#!/usr/bin/env python3
"""
Reliable benchmark orchestrator for vLLM max-num-batched-tokens experiments.

It handles four concerns:
1. Patch the target deployment to a new --max-num-batched-tokens value.
2. Wait for rollout readiness and open a stable local port-forward.
3. Run TTFT/E2E benchmarks for each (token_length, cache_rate) case.
4. Collect Thanos metrics for the exact benchmark time window.

The script intentionally keeps the request-generation logic close to bench_ttft.py
so the benchmark behavior stays familiar, but stops relying on parsing stdout.
"""

import argparse
import asyncio
import importlib.util
import json
import random
import socket
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path("~/k8s").expanduser()))
from thanos import ThanosClient


DEFAULT_BATCHED_TOKENS = [4096, 6144, 8192]
DEFAULT_TOKEN_LENGTHS = [20000, 40000, 80000, 120000]
DEFAULT_CACHE_RATES = [0.0, 0.4, 0.8]
DEFAULT_RESULT_LOG = "/tmp/maas-benchmark-result.log"
DEFAULT_NAMESPACE = "ske-model"
BENCH_MODULE_PATH = Path("/Users/humin/agent/maas/bench_ttft.py")
VLLM_PORT = 8000

NEW_TEXT_VARIANTS = [
    "在一个风雪交加的冬日",
    "在一个秋高气爽的季节",
    "在一个春意盎然的时节",
    "在一个夏日炎炎的正午",
]


@dataclass(frozen=True)
class DeploymentConfig:
    max_num_batched_tokens: int

    @property
    def name(self) -> str:
        return str(self.max_num_batched_tokens)


@dataclass(frozen=True)
class BenchmarkCase:
    token_length: int
    cache_rate: float

    @property
    def case_id(self) -> str:
        return f"{self.token_length}_{int(self.cache_rate * 100)}"


class CommandError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark max-num-batched-tokens across token lengths and cache rates."
    )
    parser.add_argument("--context", default="zz", help="kubectl context alias")
    parser.add_argument(
        "--deployment-name",
        default="minimax-m25-int8-yy",
        help="target deployment name",
    )
    parser.add_argument(
        "--metrics-service",
        default=None,
        help="service label used in vLLM Thanos queries; defaults to --deployment-name",
    )
    parser.add_argument(
        "--pods",
        nargs="+",
        default=None,
        help="explicit pod names for Thanos selector, preferred during live testing",
    )
    parser.add_argument(
        "--pod-regex",
        default=None,
        help="explicit pod regex for Thanos selector; overrides --pods and auto-discovery",
    )
    parser.add_argument(
        "--thanos-context",
        default=None,
        help="Thanos cluster alias; defaults to --context",
    )
    parser.add_argument(
        "--thanos-selector",
        default=None,
        help='explicit PromQL selector body, e.g. namespace="ske-model",pod=~"pod-a|pod-b"',
    )
    parser.add_argument(
        "--thanos-query",
        action="append",
        default=[],
        help=(
            "override metric query as name=promql; can be repeated, "
            'e.g. --thanos-query gpu=avg(nvidia_gpu_utilization_percent{pod=~"x"})'
        ),
    )
    parser.add_argument(
        "--container-index",
        type=int,
        default=0,
        help="container index inside deployment pod spec",
    )
    parser.add_argument(
        "--batched-tokens",
        type=int,
        nargs="+",
        default=DEFAULT_BATCHED_TOKENS,
        help="max-num-batched-tokens values to test",
    )
    parser.add_argument(
        "--token-lengths",
        type=int,
        nargs="+",
        default=DEFAULT_TOKEN_LENGTHS,
        help="input token lengths to test",
    )
    parser.add_argument(
        "--cache-rates",
        type=float,
        nargs="+",
        default=DEFAULT_CACHE_RATES,
        help="cache hit rates to test, e.g. 0.0 0.4 0.8",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="concurrent requests per case",
    )
    parser.add_argument(
        "--total-requests",
        type=int,
        default=16,
        help="total requests per case",
    )
    parser.add_argument(
        "--warmup-seconds",
        type=int,
        default=30,
        help="extra wait after rollout becomes ready",
    )
    parser.add_argument(
        "--rollout-timeout-seconds",
        type=int,
        default=1800,
        help="deployment rollout timeout",
    )
    parser.add_argument(
        "--port-forward-local-port",
        type=int,
        default=18000,
        help="local port for kubectl port-forward",
    )
    parser.add_argument(
        "--port-forward-timeout-seconds",
        type=int,
        default=30,
        help="timeout waiting for port-forward readiness",
    )
    parser.add_argument(
        "--result-log",
        default=DEFAULT_RESULT_LOG,
        help="output json file",
    )
    parser.add_argument(
        "--thanos-step",
        default="30s",
        help="step for thanos query_range",
    )
    parser.add_argument(
        "--thanos-trim-seconds",
        type=int,
        default=0,
        help="trim benchmark window edges before querying thanos",
    )
    parser.add_argument(
        "--restore-on-exit",
        action="store_true",
        help="restore original deployment args after the full test matrix",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=600,
        help="per request timeout for streaming responses",
    )
    return parser.parse_args()


def percentile(values: Sequence[float], ratio: float) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])

    sorted_values = sorted(float(v) for v in values)
    index = (len(sorted_values) - 1) * ratio
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def summarize_samples(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "avg": None,
            "p50": None,
            "p95": None,
        }

    numeric_values = [float(v) for v in values]
    return {
        "count": len(numeric_values),
        "min": min(numeric_values),
        "max": max(numeric_values),
        "avg": statistics.mean(numeric_values),
        "p50": percentile(numeric_values, 0.50),
        "p95": percentile(numeric_values, 0.95),
    }


def format_cmd(cmd: Sequence[str]) -> str:
    return " ".join(cmd)


def run_cmd(
    cmd: Sequence[str],
    description: str,
    timeout: int = 300,
    check: bool = True,
) -> str:
    print(f"\n>>> {description}")
    print(f"    Command: {format_cmd(cmd)}")
    result = subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if check and result.returncode != 0:
        raise CommandError(
            f"{description} failed with exit code {result.returncode}\n"
            f"STDOUT:\n{result.stdout[-1000:]}\n"
            f"STDERR:\n{result.stderr[-1000:]}"
        )

    if result.returncode != 0:
        print(f"    WARNING: exit code={result.returncode}")
        if result.stderr:
            print(f"    STDERR: {result.stderr[:500]}")

    return result.stdout


def kubectl_base_cmd(args: argparse.Namespace) -> List[str]:
    return ["kubectl", "--context", args.context, "-n", DEFAULT_NAMESPACE]


def get_deployment_json(args: argparse.Namespace) -> Dict[str, Any]:
    output = run_cmd(
        kubectl_base_cmd(args)
        + ["get", "deploy", args.deployment_name, "-o", "json"],
        description="Fetch deployment json",
        timeout=60,
    )
    return json.loads(output)


def build_label_selector(match_labels: Dict[str, str]) -> str:
    return ",".join(f"{key}={value}" for key, value in match_labels.items())


def get_container_args(
    deployment: Dict[str, Any],
    container_index: int,
) -> List[str]:
    containers = deployment["spec"]["template"]["spec"]["containers"]
    if container_index >= len(containers):
        raise CommandError(
            f"container index {container_index} out of range, only {len(containers)} containers found"
        )
    return list(containers[container_index].get("args", []))


def upsert_cli_arg(existing_args: List[str], flag: str, value: str) -> List[str]:
    updated = list(existing_args)
    for idx, arg in enumerate(updated):
        if arg == flag:
            if idx + 1 < len(updated):
                updated[idx + 1] = value
            else:
                updated.append(value)
            return updated
        if arg.startswith(f"{flag}="):
            updated[idx] = f"{flag}={value}"
            return updated

    updated.extend([flag, value])
    return updated


def patch_container_args(
    args: argparse.Namespace,
    container_index: int,
    container_args: List[str],
) -> None:
    patch_payload = [
        {
            "op": "replace",
            "path": f"/spec/template/spec/containers/{container_index}/args",
            "value": container_args,
        }
    ]
    run_cmd(
        kubectl_base_cmd(args)
        + [
            "patch",
            "deploy",
            args.deployment_name,
            "--type=json",
            "-p",
            json.dumps(patch_payload, ensure_ascii=False),
        ],
        description="Patch deployment args",
        timeout=120,
    )


def wait_for_rollout_ready(args: argparse.Namespace) -> None:
    run_cmd(
        kubectl_base_cmd(args)
        + [
            "rollout",
            "status",
            f"deploy/{args.deployment_name}",
            f"--timeout={args.rollout_timeout_seconds}s",
        ],
        description="Wait for deployment rollout",
        timeout=args.rollout_timeout_seconds + 30,
    )
    if args.warmup_seconds > 0:
        print(f"    Rollout ready, sleeping {args.warmup_seconds}s for warmup")
        time.sleep(args.warmup_seconds)


def start_port_forward(args: argparse.Namespace) -> subprocess.Popen[str]:
    cmd = kubectl_base_cmd(args) + [
        "port-forward",
        f"deploy/{args.deployment_name}",
        f"{args.port_forward_local_port}:{VLLM_PORT}",
    ]
    print("\n>>> Start port-forward")
    print(f"    Command: {format_cmd(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    deadline = time.time() + args.port_forward_timeout_seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise CommandError(
                f"port-forward exited early with code {proc.returncode}: {stderr}"
            )
        try:
            with socket.create_connection(
                ("127.0.0.1", args.port_forward_local_port), timeout=1
            ):
                print("    Port-forward is ready")
                return proc
        except OSError:
            time.sleep(1)

    proc.terminate()
    raise CommandError("port-forward did not become ready before timeout")


def stop_port_forward(proc: Optional[subprocess.Popen[str]]) -> None:
    if proc is None:
        return
    print("\n>>> Stop port-forward")
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def load_bench_module() -> Any:
    spec = importlib.util.spec_from_file_location("bench_ttft_runtime", BENCH_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise CommandError(f"failed to load bench module from {BENCH_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate_case_input(module: Any, target_tokens: int, cache_rate: float, req_id: int) -> str:
    if not getattr(module, "CACHE_BASE_TEXTS", None):
        module.init_cache_base_texts()

    available_lengths = sorted(module.CACHE_BASE_TEXTS.keys())
    closest_length = min(available_lengths, key=lambda length: abs(length - target_tokens))
    base_text = module.CACHE_BASE_TEXTS[closest_length]

    cached_tokens = int(target_tokens * cache_rate)
    new_tokens = max(target_tokens - cached_tokens, 0)
    cached_chars = cached_tokens * 2
    cached_part = base_text[:cached_chars]

    new_part_units = max(new_tokens // 40, 0)
    rng = random.Random((target_tokens * 1000) + int(cache_rate * 100) + req_id)
    new_part = []
    for _ in range(new_part_units):
        variant = rng.choice(NEW_TEXT_VARIANTS)
        new_part.append(
            f"{variant}，小红和她的同学们一起去图书馆看书。"
            "她们借阅了很多有趣的书籍和杂志。"
        )
    return cached_part + "".join(new_part)


async def run_single_case(
    module: Any,
    base_url: str,
    case: BenchmarkCase,
    concurrency: int,
    total_requests: int,
    request_timeout_seconds: int,
) -> Dict[str, Any]:
    module.BASE_URL = base_url
    module.init_cache_base_texts()

    semaphore = asyncio.Semaphore(concurrency)
    sample_results: List[Dict[str, Any]] = []

    async def measure_request(
        session: Any,
        input_text: str,
        req_id: int,
    ) -> Dict[str, Any]:
        payload = {
            "model": module.MODEL,
            "messages": [
                {"role": "user", "content": f"请用一句话总结以下内容：\n{input_text}"}
            ],
            "max_tokens": module.OUTPUT_TOKENS_PER_REQUEST,
            "temperature": 0.1,
            "stream": True,
        }

        start = time.monotonic()
        ttft = None
        e2e = None
        error = None

        try:
            async with session.post(
                base_url,
                json=payload,
                timeout=module.aiohttp.ClientTimeout(total=request_timeout_seconds),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    return {
                        "req_id": req_id,
                        "ttft": None,
                        "e2e": None,
                        "error": f"HTTP {resp.status}: {body[:200]}",
                    }

                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8").strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        if ttft is None:
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if delta.get("content") or delta.get("reasoning_content"):
                                ttft = time.monotonic() - start
                    elif line == "data: [DONE]":
                        e2e = time.monotonic() - start
                        break

                if ttft is None:
                    ttft = time.monotonic() - start
                if e2e is None:
                    e2e = time.monotonic() - start
        except Exception as exc:
            error = str(exc)

        return {"req_id": req_id, "ttft": ttft, "e2e": e2e, "error": error}

    async def bounded_request(session: Any, req_id: int) -> Dict[str, Any]:
        prompt = generate_case_input(module, case.token_length, case.cache_rate, req_id)
        async with semaphore:
            return await measure_request(session, prompt, req_id)

    async with module.aiohttp.ClientSession() as session:
        start_monotonic = time.monotonic()
        tasks = [bounded_request(session, req_id) for req_id in range(total_requests)]
        sample_results = await asyncio.gather(*tasks)
        total_time = time.monotonic() - start_monotonic

    ttfts = [sample["ttft"] for sample in sample_results if sample.get("ttft") is not None]
    e2es = [sample["e2e"] for sample in sample_results if sample.get("e2e") is not None]
    errors = [sample for sample in sample_results if sample.get("error")]

    print(
        f"    Case tokens={case.token_length}, cache={case.cache_rate:.0%}, "
        f"success={len(sample_results) - len(errors)}/{len(sample_results)}"
    )

    return {
        "token_length": case.token_length,
        "cache_rate": case.cache_rate,
        "total_requests": total_requests,
        "concurrency": concurrency,
        "request_timeout_seconds": request_timeout_seconds,
        "total_time_seconds": total_time,
        "success_count": len(sample_results) - len(errors),
        "error_count": len(errors),
        "errors": errors[:5],
        "ttft_seconds": summarize_samples(ttfts),
        "e2e_seconds": summarize_samples(e2es),
    }


def flatten_query_values(result: Dict[str, Any]) -> List[float]:
    series = result.get("data", {}).get("result", [])
    values: List[float] = []
    for item in series:
        for _, raw_value in item.get("values", []):
            try:
                values.append(float(raw_value))
            except (TypeError, ValueError):
                continue
    return values


def parse_named_queries(raw_queries: Sequence[str]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for raw_query in raw_queries:
        if "=" not in raw_query:
            raise CommandError(
                f"invalid --thanos-query value {raw_query!r}, expected name=promql"
            )
        name, promql = raw_query.split("=", 1)
        metric_name = name.strip()
        promql_value = promql.strip()
        if not metric_name or not promql_value:
            raise CommandError(
                f"invalid --thanos-query value {raw_query!r}, expected non-empty name and promql"
            )
        parsed[metric_name] = promql_value
    return parsed


def build_selector_candidates(namespace: str, pod_regex: str) -> List[str]:
    candidates = [
        f'namespace="{namespace}",pod=~"{pod_regex}"',
        f'exported_namespace="{namespace}",pod=~"{pod_regex}"',
        f'namespace="{namespace}",pod_name=~"{pod_regex}"',
        f'exported_namespace="{namespace}",pod_name=~"{pod_regex}"',
        f'pod=~"{pod_regex}"',
        f'pod_name=~"{pod_regex}"',
    ]

    deduplicated: List[str] = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            deduplicated.append(candidate)
            seen.add(candidate)
    return deduplicated


def build_default_thanos_queries(
    metrics_namespace: str,
    metrics_service: str,
    pod_selectors: Sequence[str],
) -> Dict[str, List[str]]:
    pod_selector_candidates = list(pod_selectors) if pod_selectors else [""]
    vllm_selector = (
        f'namespace="{metrics_namespace}",service=~"{metrics_service}",framework="vllm"'
    )

    def pod_scoped(metric: str, aggregator: str = "avg") -> List[str]:
        queries = []
        for selector in pod_selector_candidates:
            scoped_metric = f"{metric}{{{selector}}}" if selector else metric
            queries.append(f"{aggregator}({scoped_metric})")
        return queries

    return {
        "vllm_num_requests_waiting": [
            f"sum by (service) (vllm:num_requests_waiting{{{vllm_selector}}})"
        ],
        "vllm_num_requests_running": [
            f"sum by (service) (vllm:num_requests_running{{{vllm_selector}}})"
        ],
        "vllm_e2e_p90_seconds": [
            "histogram_quantile(0.9, "
            f"sum by(le, service) (rate(vllm:e2e_request_latency_seconds_bucket{{{vllm_selector}}}[5m])))"
        ],
        "vllm_prompt_tokens_tps": [
            f"sum by (service) (rate(vllm:prompt_tokens_total{{{vllm_selector}}}[5m]))"
        ],
        "vllm_generation_tokens_tps": [
            f"sum by (service) (rate(vllm:generation_tokens_total{{{vllm_selector}}}[5m]))"
        ],
        "vllm_ttft_p90_seconds": [
            "histogram_quantile(0.9, "
            f"sum by(le, service) (rate(vllm:time_to_first_token_seconds_bucket{{{vllm_selector}}}[5m])))"
        ],
        "vllm_prefix_cache_hit_rate": [
            "(sum by (service) "
            f"(rate(vllm:gpu_prefix_cache_hits_total{{{vllm_selector}}}[5m])) / "
            "clamp_min(sum by (service) "
            f"(rate(vllm:gpu_prefix_cache_queries_total{{{vllm_selector}}}[5m])), 1e-10)) or "
            "(sum by (service) "
            f"(rate(vllm:prefix_cache_hits_total{{{vllm_selector}}}[5m])) / "
            "clamp_min(sum by (service) "
            f"(rate(vllm:prefix_cache_queries_total{{{vllm_selector}}}[5m])), 1e-10))"
        ],
        "vllm_kv_cache_usage_percent": [
            f"avg by (service) (vllm:kv_cache_usage_perc{{{vllm_selector}}})"
        ],
        "gpu_utilization_percent": pod_scoped("nvidia_gpu_utilization_percent"),
    }


def collect_thanos_metrics(
    thanos_context: str,
    queries: Dict[str, List[str]],
    start_time: datetime,
    end_time: datetime,
    step: str,
    trim_seconds: int,
) -> Dict[str, Any]:
    query_start = start_time.timestamp() + trim_seconds
    query_end = end_time.timestamp() - trim_seconds
    if query_start >= query_end:
        query_start = start_time.timestamp()
        query_end = end_time.timestamp()

    client = ThanosClient(thanos_context)
    metrics: Dict[str, Any] = {
        "window": {
            "start_time": datetime.fromtimestamp(query_start).isoformat(),
            "end_time": datetime.fromtimestamp(query_end).isoformat(),
            "step": step,
            "trim_seconds": trim_seconds,
        },
        "queries": queries,
        "results": {},
    }

    for name, promql_candidates in queries.items():
        attempts = []
        selected_result = None
        for promql in promql_candidates:
            try:
                result = client.query_range(promql, start=query_start, end=query_end, step=step)
                values = flatten_query_values(result)
                attempt = {
                    "promql": promql,
                    "series_count": len(result.get("data", {}).get("result", [])),
                    "sample_count": len(values),
                }
                attempts.append(attempt)
                if values and selected_result is None:
                    selected_result = {
                        "promql": promql,
                        "values": values,
                        "series_count": attempt["series_count"],
                    }
            except Exception as exc:
                attempts.append({"promql": promql, "error": str(exc)})

        if selected_result is not None:
            metrics["results"][name] = {
                "selected_promql": selected_result["promql"],
                "summary": summarize_samples(selected_result["values"]),
                "series_count": selected_result["series_count"],
                "attempts": attempts,
            }
        else:
            metrics["results"][name] = {
                "error": "no thanos query candidate returned samples",
                "attempts": attempts,
            }

    return metrics


def get_pod_regex(args: argparse.Namespace, deployment: Dict[str, Any]) -> str:
    if args.pod_regex:
        return args.pod_regex

    if args.pods:
        return "|".join(sorted(args.pods))

    match_labels = deployment["spec"]["selector"]["matchLabels"]
    label_selector = build_label_selector(match_labels)
    output = run_cmd(
        kubectl_base_cmd(args)
        + [
            "get",
            "pods",
            "-l",
            label_selector,
            "-o",
            "json",
        ],
        description="Fetch deployment pods",
        timeout=60,
    )
    pod_items = json.loads(output).get("items", [])
    pod_names = sorted(item["metadata"]["name"] for item in pod_items)
    if not pod_names:
        raise CommandError("no pods found for deployment selector")
    return "|".join(pod_names)


def print_execution_summary(args: argparse.Namespace) -> None:
    total_cases = len(args.batched_tokens) * len(args.token_lengths) * len(args.cache_rates)
    metrics_service = args.metrics_service or args.deployment_name
    print("=" * 100)
    print("vLLM max-num-batched-tokens benchmark")
    print("=" * 100)
    print(f"Context: {args.context}")
    print(f"Namespace: {DEFAULT_NAMESPACE}")
    print(f"Deployment: {args.deployment_name}")
    print(f"Metrics namespace: {DEFAULT_NAMESPACE}")
    print(f"Metrics service: {metrics_service}")
    print(f"Batched tokens: {args.batched_tokens}")
    print(f"Token lengths: {args.token_lengths}")
    print(f"Cache rates: {args.cache_rates}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Total requests/case: {args.total_requests}")
    print(f"Total cases: {total_cases}")
    print(f"Result log: {args.result_log}")


def save_results(result_log: str, payload: Dict[str, Any]) -> None:
    path = Path(result_log)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n>>> Results saved to {path}")


async def orchestrate(args: argparse.Namespace) -> Dict[str, Any]:
    bench_module = load_bench_module()
    base_url = f"http://127.0.0.1:{args.port_forward_local_port}/v1/chat/completions"
    metrics_service = args.metrics_service or args.deployment_name

    print_execution_summary(args)

    deployment = get_deployment_json(args)
    original_args = get_container_args(deployment, args.container_index)
    pod_regex = get_pod_regex(args, deployment)
    pod_selector_candidates = (
        [args.thanos_selector]
        if args.thanos_selector
        else build_selector_candidates(DEFAULT_NAMESPACE, pod_regex)
    )
    thanos_queries = build_default_thanos_queries(
        metrics_namespace=DEFAULT_NAMESPACE,
        metrics_service=metrics_service,
        pod_selectors=pod_selector_candidates,
    )
    thanos_queries.update(
        {
            name: [promql]
            for name, promql in parse_named_queries(args.thanos_query).items()
        }
    )

    all_results: Dict[str, Any] = {
        "test_start_time": datetime.now().isoformat(),
        "target": {
            "context": args.context,
            "namespace": DEFAULT_NAMESPACE,
            "deployment_name": args.deployment_name,
            "thanos_context": args.thanos_context or args.context,
            "container_index": args.container_index,
            "metrics_namespace": DEFAULT_NAMESPACE,
            "metrics_service": metrics_service,
        },
        "parameters": {
            "batched_tokens": args.batched_tokens,
            "token_lengths": args.token_lengths,
            "cache_rates": args.cache_rates,
            "concurrency": args.concurrency,
            "total_requests": args.total_requests,
            "warmup_seconds": args.warmup_seconds,
            "thanos_step": args.thanos_step,
            "thanos_trim_seconds": args.thanos_trim_seconds,
            "request_timeout_seconds": args.request_timeout_seconds,
        },
        "baseline": {
            "original_container_args": original_args,
            "pod_regex": pod_regex,
            "thanos_selector_candidates": pod_selector_candidates,
            "thanos_queries": thanos_queries,
        },
        "results": [],
        "restore_on_exit": args.restore_on_exit,
        "restored": False,
        "test_end_time": None,
    }

    for batched_tokens in args.batched_tokens:
        config = DeploymentConfig(max_num_batched_tokens=batched_tokens)
        print("\n" + "=" * 100)
        print(f"Testing max-num-batched-tokens={config.max_num_batched_tokens}")
        print("=" * 100)

        updated_args = upsert_cli_arg(
            original_args,
            "--max-num-batched-tokens",
            str(config.max_num_batched_tokens),
        )

        config_result: Dict[str, Any] = {
            "config": asdict(config),
            "deployment_patch_args": updated_args,
            "cases": [],
            "error": None,
        }

        port_forward_proc: Optional[subprocess.Popen[str]] = None
        try:
            patch_container_args(args, args.container_index, updated_args)
            wait_for_rollout_ready(args)
            port_forward_proc = start_port_forward(args)

            for token_length in args.token_lengths:
                for cache_rate in args.cache_rates:
                    case = BenchmarkCase(token_length=token_length, cache_rate=cache_rate)
                    print(
                        f"\n>>> Run case tokens={case.token_length}, cache_rate={case.cache_rate:.0%}"
                    )
                    case_start = datetime.now()
                    benchmark_summary = await run_single_case(
                        module=bench_module,
                        base_url=base_url,
                        case=case,
                        concurrency=args.concurrency,
                        total_requests=args.total_requests,
                        request_timeout_seconds=args.request_timeout_seconds,
                    )
                    case_end = datetime.now()
                    thanos_metrics = collect_thanos_metrics(
                        thanos_context=args.thanos_context or args.context,
                        queries=thanos_queries,
                        start_time=case_start,
                        end_time=case_end,
                        step=args.thanos_step,
                        trim_seconds=args.thanos_trim_seconds,
                    )
                    config_result["cases"].append(
                        {
                            "case": asdict(case),
                            "start_time": case_start.isoformat(),
                            "end_time": case_end.isoformat(),
                            "benchmark": benchmark_summary,
                            "thanos": thanos_metrics,
                        }
                    )
        except Exception as exc:
            config_result["error"] = str(exc)
        finally:
            stop_port_forward(port_forward_proc)

        all_results["results"].append(config_result)
        save_results(args.result_log, all_results)

    if args.restore_on_exit:
        print("\n>>> Restore original deployment args")
        patch_container_args(args, args.container_index, original_args)
        wait_for_rollout_ready(args)
        all_results["restored"] = True

    all_results["test_end_time"] = datetime.now().isoformat()
    save_results(args.result_log, all_results)
    return all_results


def main() -> int:
    args = parse_args()
    try:
        asyncio.run(orchestrate(args))
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as exc:
        print(f"\nERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
