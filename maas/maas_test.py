#!/usr/bin/env python3
"""
Maas benchmark toolkit.

- Public-ingress benchmark entrypoint lives in this file.
- Shared benchmark helpers also live here so maas_tune.py can reuse them.
"""

import argparse
import asyncio
import json
import random
import re
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
DEFAULT_OUTPUT_TOKENS_PER_REQUEST = 256
DEFAULT_CONCURRENCY = 24
DEFAULT_BENCHMARK_MODE = "fixed"
INGRESS_HTTP_PORT = 58000
CLUSTER_DOMAINS = {
    "zz": "zzai2.scnet.cn",
    "ks": "ksai.scnet.cn",
}

CACHE_BASE_TEXTS: Dict[int, str] = {}
BASE_TEXT_VARIANTS = [
    "在一个阳光明媚的早晨",
    "在一个风和日丽的下午",
    "在一个星空灿烂的夜晚",
    "在一个细雨蒙蒙的黄昏",
]
NEW_TEXT_VARIANTS = [
    "在一个风雪交加的冬日",
    "在一个秋高气爽的季节",
    "在一个春意盎然的时节",
    "在一个夏日炎炎的正午",
]


@dataclass(frozen=True)
class DeploymentConfig:
    max_num_batched_tokens: int


@dataclass(frozen=True)
class BenchmarkCase:
    token_length: int
    cache_rate: float


class CommandError(RuntimeError):
    pass


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--context", default="zz", help="kubectl context alias")
    parser.add_argument(
        "--deployment-name",
        default="minimax-m25-int8-yy",
        help="target deployment name",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="model name for API requests; auto-detected from /v1/models if omitted",
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
        default=DEFAULT_CONCURRENCY,
        help="concurrent requests per case",
    )
    parser.add_argument(
        "--total-requests",
        type=int,
        default=48,
        help="total requests per case (fixed mode)",
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
        "--request-timeout-seconds",
        type=int,
        default=600,
        help="per request timeout for streaming responses",
    )
    parser.add_argument(
        "--benchmark-mode",
        choices=["fixed", "sustained"],
        default=DEFAULT_BENCHMARK_MODE,
        help="fixed runs a bounded request count, sustained keeps pressure for a fixed duration",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=600,
        help="duration for sustained mode",
    )
    parser.add_argument(
        "--report-interval-seconds",
        type=int,
        default=30,
        help="live report interval for sustained mode",
    )
    parser.add_argument(
        "--output-tokens",
        type=int,
        default=DEFAULT_OUTPUT_TOKENS_PER_REQUEST,
        help="max_tokens per request",
    )
    parser.add_argument(
        "--warmup-seconds",
        type=int,
        default=30,
        help="extra wait after target becomes ready",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="explicit chat completions URL; defaults to derived ingress URL",
    )


def validate_common_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> argparse.Namespace:
    if args.concurrency <= 0:
        parser.error("--concurrency must be > 0")
    if args.total_requests <= 0:
        parser.error("--total-requests must be > 0")
    if args.duration_seconds <= 0:
        parser.error("--duration-seconds must be > 0")
    if args.report_interval_seconds <= 0:
        parser.error("--report-interval-seconds must be > 0")
    if args.output_tokens <= 0:
        parser.error("--output-tokens must be > 0")
    return args


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


def format_latency_summary(summary: Dict[str, Optional[float]], name: str) -> str:
    if not summary.get("count"):
        return f"  {name}: (no data)"
    return (
        f"  {name}: min={summary['min']:.2f}s, avg={summary['avg']:.2f}s, "
        f"p50={summary['p50']:.2f}s, p95={summary['p95']:.2f}s, max={summary['max']:.2f}s"
    )


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


def kubectl_base_cmd(context: str, namespace: str = DEFAULT_NAMESPACE) -> List[str]:
    return ["kubectl", "--context", context, "-n", namespace]


def generate_fixed_input(target_tokens: int, seed: int = 42) -> str:
    rng = random.Random(seed)
    units_needed = target_tokens // 40
    parts = []
    for _ in range(units_needed):
        variant = rng.choice(BASE_TEXT_VARIANTS)
        parts.append(
            f"{variant}，小明和他的朋友们一起去公园散步。"
            "他们看到了很多美丽的花朵和高大的树木。"
        )
    return "".join(parts)


def init_cache_base_texts(token_lengths: Sequence[int]) -> None:
    if CACHE_BASE_TEXTS:
        return
    for length in sorted(set(list(token_lengths) + [26000, 50000])):
        CACHE_BASE_TEXTS[length] = generate_fixed_input(length, seed=42)


def generate_case_input(target_tokens: int, cache_rate: float, req_id: int) -> str:
    init_cache_base_texts(DEFAULT_TOKEN_LENGTHS)
    available_lengths = sorted(CACHE_BASE_TEXTS.keys())
    closest_length = min(available_lengths, key=lambda length: abs(length - target_tokens))
    base_text = CACHE_BASE_TEXTS[closest_length]
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


def detect_model(base_url: str, timeout: int = 30) -> str:
    import urllib.request

    models_url = base_url.rsplit("/v1/", 1)[0] + "/v1/models"
    print(f"\n>>> Auto-detecting model from {models_url}")
    try:
        req = urllib.request.Request(models_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            if models:
                model_id = models[0]["id"]
                print(f"    Detected model: {model_id}")
                return model_id
    except Exception as exc:
        print(f"    WARNING: model auto-detection failed: {exc}")
    raise CommandError("could not auto-detect model; pass --model explicitly")


async def measure_streaming_request(
    session: Any,
    base_url: str,
    input_text: str,
    req_id: int,
    request_timeout_seconds: int,
    output_tokens: int,
    model: str,
) -> Dict[str, Any]:
    import aiohttp

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": f"请详细分析以下内容并给出你的见解：\n{input_text}"}],
        "max_tokens": output_tokens,
        "temperature": 0.1,
        "stream": True,
    }
    start = time.monotonic()
    ttft = None
    e2e = None
    generated_tokens = 0
    error = None
    try:
        async with session.post(
            base_url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=request_timeout_seconds),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                return {
                    "req_id": req_id,
                    "ttft": None,
                    "e2e": None,
                    "generated_tokens": 0,
                    "error": f"HTTP {resp.status}: {body[:200]}",
                }
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunk = json.loads(line[6:])
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = (
                        delta.get("content")
                        or delta.get("reasoning_content")
                        or delta.get("reasoning")
                    )
                    if content:
                        if ttft is None:
                            ttft = time.monotonic() - start
                        generated_tokens += 1
                elif line == "data: [DONE]":
                    e2e = time.monotonic() - start
                    break
            if ttft is None:
                ttft = time.monotonic() - start
            if e2e is None:
                e2e = time.monotonic() - start
    except Exception as exc:
        error = str(exc)[:200]
    return {
        "req_id": req_id,
        "ttft": ttft,
        "e2e": e2e,
        "generated_tokens": generated_tokens,
        "error": error,
    }


async def run_fixed_case(
    base_url: str,
    case: BenchmarkCase,
    concurrency: int,
    total_requests: int,
    request_timeout_seconds: int,
    output_tokens: int,
    model: str,
) -> Dict[str, Any]:
    import aiohttp

    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_request(session: Any, req_id: int) -> Dict[str, Any]:
        prompt = generate_case_input(case.token_length, case.cache_rate, req_id)
        async with semaphore:
            return await measure_streaming_request(
                session=session,
                base_url=base_url,
                input_text=prompt,
                req_id=req_id,
                request_timeout_seconds=request_timeout_seconds,
                output_tokens=output_tokens,
                model=model,
            )

    async with aiohttp.ClientSession() as session:
        start_monotonic = time.monotonic()
        tasks = [bounded_request(session, req_id) for req_id in range(total_requests)]
        sample_results = await asyncio.gather(*tasks)
        total_time = time.monotonic() - start_monotonic

    successes = [s for s in sample_results if not s.get("error")]
    errors = [s for s in sample_results if s.get("error")]
    ttfts = [s["ttft"] for s in successes if s.get("ttft") is not None]
    e2es = [s["e2e"] for s in successes if s.get("e2e") is not None]
    generated_tokens = [float(s["generated_tokens"]) for s in successes]
    total_generated_tokens = sum(generated_tokens)
    effective_input_tokens = case.token_length * (1 - case.cache_rate) * len(successes)
    weighted_tokens = effective_input_tokens * 1 + total_generated_tokens * 10
    tpm = (weighted_tokens / total_time * 60) if total_time > 0 else 0.0
    tpm_per_user = tpm / concurrency if concurrency > 0 else 0.0
    ttft_summary = summarize_samples(ttfts)
    e2e_summary = summarize_samples(e2es)
    print(
        f"    Case tokens={case.token_length}, cache={case.cache_rate:.0%}, "
        f"success={len(successes)}/{len(sample_results)}, "
        f"TPM={tpm:.0f}, TPM/user={tpm_per_user:.0f}"
    )
    print(format_latency_summary(ttft_summary, "TTFT"))
    print(format_latency_summary(e2e_summary, " E2E"))
    return {
        "mode": "fixed",
        "token_length": case.token_length,
        "cache_rate": case.cache_rate,
        "total_requests": total_requests,
        "concurrency": concurrency,
        "request_timeout_seconds": request_timeout_seconds,
        "total_time_seconds": total_time,
        "success_count": len(successes),
        "error_count": len(errors),
        "errors": [{"req_id": e["req_id"], "error": e["error"][:100]} for e in errors[:5]],
        "generated_tokens": {
            "per_request": summarize_samples(generated_tokens),
            "total": total_generated_tokens,
        },
        "throughput": {
            "tpm": tpm,
            "tpm_per_user": tpm_per_user,
            "effective_input_tokens": effective_input_tokens,
            "output_tokens": total_generated_tokens,
            "weighted_tokens": weighted_tokens,
        },
        "ttft_seconds": ttft_summary,
        "e2e_seconds": e2e_summary,
    }


async def run_sustained_case(
    base_url: str,
    case: BenchmarkCase,
    concurrency: int,
    duration_seconds: int,
    request_timeout_seconds: int,
    report_interval_seconds: int,
    output_tokens: int,
    model: str,
) -> Dict[str, Any]:
    import aiohttp

    semaphore = asyncio.Semaphore(concurrency)
    stats: Dict[str, Any] = {
        "success_count": 0,
        "error_count": 0,
        "submitted_requests": 0,
        "generated_tokens_total": 0,
        "ttfts": [],
        "e2es": [],
        "error_samples": [],
        "timeline": [],
    }
    stop_event = asyncio.Event()

    async def worker(session: Any, worker_id: int) -> None:
        req_id = worker_id * 100000
        consecutive_errors = 0
        while not stop_event.is_set():
            prompt = generate_case_input(case.token_length, case.cache_rate, req_id)
            async with semaphore:
                if stop_event.is_set():
                    break
                result = await measure_streaming_request(
                    session=session,
                    base_url=base_url,
                    input_text=prompt,
                    req_id=req_id,
                    request_timeout_seconds=request_timeout_seconds,
                    output_tokens=output_tokens,
                    model=model,
                )
            stats["submitted_requests"] += 1
            if result.get("error"):
                stats["error_count"] += 1
                consecutive_errors += 1
                if len(stats["error_samples"]) < 10:
                    stats["error_samples"].append({
                        "req_id": result["req_id"],
                        "error": result["error"][:100],
                    })
                await asyncio.sleep(min(2 ** consecutive_errors, 30))
            else:
                consecutive_errors = 0
                stats["success_count"] += 1
                stats["generated_tokens_total"] += result.get("generated_tokens", 0)
                if result.get("ttft") is not None:
                    stats["ttfts"].append(result["ttft"])
                if result.get("e2e") is not None:
                    stats["e2es"].append(result["e2e"])
            req_id += 1

    async def reporter(start_monotonic: float) -> None:
        while not stop_event.is_set():
            await asyncio.sleep(report_interval_seconds)
            if stop_event.is_set():
                break
            elapsed = time.monotonic() - start_monotonic
            total = stats["success_count"] + stats["error_count"]
            recent_ttfts = stats["ttfts"][-concurrency:] if stats["ttfts"] else []
            recent_e2es = stats["e2es"][-concurrency:] if stats["e2es"] else []
            avg_ttft = statistics.mean(recent_ttfts) if recent_ttfts else 0.0
            avg_e2e = statistics.mean(recent_e2es) if recent_e2es else 0.0
            effective_input_tokens_current = case.token_length * (1 - case.cache_rate) * stats["success_count"]
            weighted_tokens_current = effective_input_tokens_current * 1 + stats["generated_tokens_total"] * 10
            tpm_current = (weighted_tokens_current / elapsed * 60) if elapsed > 0 else 0.0
            tpm_per_user_current = tpm_current / concurrency if concurrency > 0 else 0.0
            snapshot = {
                "elapsed_s": round(elapsed),
                "total": total,
                "success": stats["success_count"],
                "errors": stats["error_count"],
                "tpm": round(tpm_current, 0),
                "tpm_per_user": round(tpm_per_user_current, 0),
                "recent_avg_ttft": round(avg_ttft, 1),
                "recent_avg_e2e": round(avg_e2e, 1),
            }
            stats["timeline"].append(snapshot)
            print(
                f"  [{elapsed:6.0f}s] total={total}, success={stats['success_count']}, "
                f"errors={stats['error_count']}, TPM={tpm_current:.0f}, TPM/user={tpm_per_user_current:.0f}, "
                f"recent_avg_ttft={avg_ttft:.1f}s, recent_avg_e2e={avg_e2e:.1f}s"
            )

    print(
        f"\n=== Sustained: tokens={case.token_length}, cache={case.cache_rate:.0%}, "
        f"concurrency={concurrency}, duration={duration_seconds}s ==="
    )
    print(f"    URL: {base_url}")
    print(f"    Start: {datetime.now().isoformat()}")
    start_monotonic = time.monotonic()
    connector = aiohttp.TCPConnector(limit=concurrency, limit_per_host=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        workers = [asyncio.create_task(worker(session, worker_id)) for worker_id in range(concurrency)]
        report_task = asyncio.create_task(reporter(start_monotonic))
        try:
            await asyncio.sleep(duration_seconds)
        finally:
            stop_event.set()
            for task in workers:
                task.cancel()
            report_task.cancel()
            await asyncio.gather(*workers, report_task, return_exceptions=True)

    total_time = time.monotonic() - start_monotonic
    ttft_summary = summarize_samples(stats["ttfts"])
    e2e_summary = summarize_samples(stats["e2es"])
    effective_input_tokens_final = case.token_length * (1 - case.cache_rate) * stats["success_count"]
    weighted_tokens_final = effective_input_tokens_final * 1 + stats["generated_tokens_total"] * 10
    tpm_final = (weighted_tokens_final / total_time * 60) if total_time > 0 else 0.0
    tpm_per_user_final = tpm_final / concurrency if concurrency > 0 else 0.0
    print(f"\n    End: {datetime.now().isoformat()}")
    print(f"    Wall time: {total_time:.1f}s")
    print(f"    Success: {stats['success_count']}, Errors: {stats['error_count']}")
    print(f"    Effective input tokens: {effective_input_tokens_final}")
    print(f"    Total output tokens: {stats['generated_tokens_total']}")
    print(f"    Overall TPM: {tpm_final:.0f}, TPM/user: {tpm_per_user_final:.0f}")
    print(format_latency_summary(ttft_summary, "TTFT"))
    print(format_latency_summary(e2e_summary, " E2E"))
    return {
        "mode": "sustained",
        "token_length": case.token_length,
        "cache_rate": case.cache_rate,
        "duration_seconds": duration_seconds,
        "concurrency": concurrency,
        "request_timeout_seconds": request_timeout_seconds,
        "report_interval_seconds": report_interval_seconds,
        "total_time_seconds": total_time,
        "submitted_requests": stats["submitted_requests"],
        "success_count": stats["success_count"],
        "error_count": stats["error_count"],
        "errors": stats["error_samples"],
        "generated_tokens": {
            "total": stats["generated_tokens_total"],
        },
        "throughput": {
            "tpm": tpm_final,
            "tpm_per_user": tpm_per_user_final,
            "effective_input_tokens": effective_input_tokens_final,
            "output_tokens": stats["generated_tokens_total"],
            "weighted_tokens": weighted_tokens_final,
        },
        "ttft_seconds": ttft_summary,
        "e2e_seconds": e2e_summary,
        "timeline": stats["timeline"],
    }


async def run_single_case(
    base_url: str,
    case: BenchmarkCase,
    benchmark_mode: str,
    concurrency: int,
    total_requests: int,
    duration_seconds: int,
    request_timeout_seconds: int,
    report_interval_seconds: int,
    output_tokens: int,
    model: str,
) -> Dict[str, Any]:
    if benchmark_mode == "sustained":
        return await run_sustained_case(
            base_url=base_url,
            case=case,
            concurrency=concurrency,
            duration_seconds=duration_seconds,
            request_timeout_seconds=request_timeout_seconds,
            report_interval_seconds=report_interval_seconds,
            output_tokens=output_tokens,
            model=model,
        )
    return await run_fixed_case(
        base_url=base_url,
        case=case,
        concurrency=concurrency,
        total_requests=total_requests,
        request_timeout_seconds=request_timeout_seconds,
        output_tokens=output_tokens,
        model=model,
    )


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
            raise CommandError(f"invalid --thanos-query value {raw_query!r}, expected name=promql")
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
    pod_regex: str = "",
) -> Dict[str, List[str]]:
    dcu_selector_candidates = []
    if pod_regex:
        dcu_selector_candidates = [
            f'dcu_pod_namespace="{metrics_namespace}",dcu_pod_name=~"{pod_regex}"',
        ]

    def dcu_scoped(metric: str, aggregator: str = "avg") -> List[str]:
        queries = []
        for selector in dcu_selector_candidates:
            queries.append(f"{aggregator}({metric}{{{selector}}})")
        if not queries:
            queries = [f"{aggregator}({metric})"]
        return queries

    return {
        "dcu_utilization_percent": dcu_scoped("dcu_container_dcu_util"),
        "dcu_mem_utilization_percent": dcu_scoped("dcu_container_mem_util"),
        "dcu_power_watts": dcu_scoped("dcu_power_usage"),
        "dcu_hbm_bandwidth_mbps": dcu_scoped("dcu_df_bw_read_write"),
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
                attempts.append({"promql": promql, "error": str(exc)[:200]})

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


def save_results(result_log: str, payload: Dict[str, Any]) -> None:
    path = Path(result_log)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n>>> Results saved to {path}")


def get_deployment_json(context: str, deployment_name: str, namespace: str = DEFAULT_NAMESPACE) -> Dict[str, Any]:
    output = run_cmd(
        kubectl_base_cmd(context, namespace) + ["get", "deploy", deployment_name, "-o", "json"],
        description="Fetch deployment json",
        timeout=60,
    )
    return json.loads(output)


def build_label_selector(match_labels: Dict[str, str]) -> str:
    return ",".join(f"{key}={value}" for key, value in match_labels.items())


def get_container_args(deployment: Dict[str, Any], container_index: int) -> List[str]:
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
    context: str,
    deployment_name: str,
    container_index: int,
    container_args: List[str],
    namespace: str = DEFAULT_NAMESPACE,
) -> None:
    patch_payload = [
        {
            "op": "replace",
            "path": f"/spec/template/spec/containers/{container_index}/args",
            "value": container_args,
        }
    ]
    run_cmd(
        kubectl_base_cmd(context, namespace)
        + [
            "patch",
            "deploy",
            deployment_name,
            "--type=json",
            "-p",
            json.dumps(patch_payload, ensure_ascii=False),
        ],
        description="Patch deployment args",
        timeout=120,
    )


def wait_for_rollout_ready(
    context: str,
    deployment_name: str,
    rollout_timeout_seconds: int,
    warmup_seconds: int = 0,
    namespace: str = DEFAULT_NAMESPACE,
) -> None:
    run_cmd(
        kubectl_base_cmd(context, namespace)
        + [
            "rollout",
            "status",
            f"deploy/{deployment_name}",
            f"--timeout={rollout_timeout_seconds}s",
        ],
        description="Wait for deployment rollout",
        timeout=rollout_timeout_seconds + 30,
    )
    if warmup_seconds > 0:
        print(f"    Target ready, sleeping {warmup_seconds}s for warmup")
        time.sleep(warmup_seconds)


def get_pod_regex(
    context: str,
    deployment: Dict[str, Any],
    deployment_name: str,
    explicit_pods: Optional[Sequence[str]] = None,
    explicit_pod_regex: Optional[str] = None,
    namespace: str = DEFAULT_NAMESPACE,
) -> str:
    if explicit_pod_regex:
        return explicit_pod_regex
    if explicit_pods:
        return "|".join(sorted(explicit_pods))

    match_labels = deployment["spec"]["selector"]["matchLabels"]
    label_selector = build_label_selector(match_labels)
    output = run_cmd(
        kubectl_base_cmd(context, namespace) + ["get", "pods", "-l", label_selector, "-o", "json"],
        description=f"Fetch pods for deployment {deployment_name}",
        timeout=60,
    )
    pod_items = json.loads(output).get("items", [])
    pod_names = sorted(item["metadata"]["name"] for item in pod_items)
    if not pod_names:
        raise CommandError("no pods found for deployment selector")
    return "|".join(pod_names)


def print_benchmark_summary(args: argparse.Namespace, title: str, extra_lines: Optional[Sequence[str]] = None) -> None:
    total_cases = len(args.token_lengths) * len(args.cache_rates)
    metrics_service = args.metrics_service or args.deployment_name
    target_label = "Pod" if getattr(args, "pod", None) else "Deployment"
    target_value = getattr(args, "pod", None) or args.deployment_name
    print("=" * 100)
    print(title)
    print("=" * 100)
    print(f"Context: {args.context}")
    print(f"Namespace: {args.namespace}")
    print(f"{target_label}: {target_value}")
    print(f"Model: {args.model or '(auto-detect)'}")
    print(f"Metrics namespace: {args.metrics_namespace}")
    print(f"Metrics service: {metrics_service}")
    print(f"Token lengths: {args.token_lengths}")
    print(f"Cache rates: {args.cache_rates}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Benchmark mode: {args.benchmark_mode}")
    if args.benchmark_mode == "fixed":
        print(f"Total requests/case: {args.total_requests}")
    else:
        print(f"Duration/case: {args.duration_seconds}s")
        print(f"Report interval: {args.report_interval_seconds}s")
    print(f"Output tokens/request: {args.output_tokens}")
    print(f"Total cases: {total_cases}")
    print(f"Result log: {args.result_log}")
    if extra_lines:
        for line in extra_lines:
            print(line)


def build_ingress_base_url(context: str, deployment_name: str) -> str:
    if context not in CLUSTER_DOMAINS:
        raise CommandError(
            f"no ingress domain mapping for context {context!r}; pass --base-url explicitly"
        )
    domain = CLUSTER_DOMAINS[context]
    return f"http://{deployment_name}.{domain}:{INGRESS_HTTP_PORT}/v1/chat/completions"


def resolve_model(args: argparse.Namespace, base_url: str) -> str:
    if args.model:
        return args.model
    return detect_model(base_url)


async def run_benchmark_matrix(
    *,
    args: argparse.Namespace,
    base_url: str,
    metrics_service: str,
    pod_regex: str,
    result_prefix: Dict[str, Any],
    save_intermediate: bool = True,
) -> Dict[str, Any]:
    model = resolve_model(args, base_url)
    thanos_queries = build_default_thanos_queries(
        metrics_namespace=args.metrics_namespace,
        pod_regex=pod_regex,
    )
    thanos_queries.update({name: [promql] for name, promql in parse_named_queries(args.thanos_query).items()})
    all_results: Dict[str, Any] = {
        "test_start_time": datetime.now().isoformat(),
        "target": result_prefix["target"],
        "parameters": {
            "model": model,
            "token_lengths": args.token_lengths,
            "cache_rates": args.cache_rates,
            "concurrency": args.concurrency,
            "total_requests": args.total_requests,
            "benchmark_mode": args.benchmark_mode,
            "duration_seconds": args.duration_seconds,
            "report_interval_seconds": args.report_interval_seconds,
            "warmup_seconds": args.warmup_seconds,
            "thanos_step": args.thanos_step,
            "thanos_trim_seconds": args.thanos_trim_seconds,
            "request_timeout_seconds": args.request_timeout_seconds,
            "output_tokens": args.output_tokens,
        },
        "baseline": {
            **result_prefix.get("baseline", {}),
            "pod_regex": pod_regex,
            "thanos_queries": thanos_queries,
        },
        "results": [],
        "test_end_time": None,
    }

    for token_length in args.token_lengths:
        for cache_rate in args.cache_rates:
            case = BenchmarkCase(token_length=token_length, cache_rate=cache_rate)
            print(f"\n>>> Run case tokens={case.token_length}, cache_rate={case.cache_rate:.0%}")
            case_start = datetime.now()
            benchmark_summary = await run_single_case(
                base_url=base_url,
                case=case,
                benchmark_mode=args.benchmark_mode,
                concurrency=args.concurrency,
                total_requests=args.total_requests,
                duration_seconds=args.duration_seconds,
                request_timeout_seconds=args.request_timeout_seconds,
                report_interval_seconds=args.report_interval_seconds,
                output_tokens=args.output_tokens,
                model=model,
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
            all_results["results"].append(
                {
                    "case": asdict(case),
                    "start_time": case_start.isoformat(),
                    "end_time": case_end.isoformat(),
                    "benchmark": benchmark_summary,
                    "thanos": thanos_metrics,
                }
            )
            if save_intermediate:
                save_results(args.result_log, all_results)

    all_results["test_end_time"] = datetime.now().isoformat()
    if save_intermediate:
        save_results(args.result_log, all_results)
    return all_results


def build_public_ingress_base_url(context: str, deployment_name: str) -> str:
    return build_ingress_base_url(context, deployment_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark one vLLM deployment via public ingress HTTP endpoint.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  uv run %(prog)s --context zz --deployment-name minimax-m25-int8-vip \
      --token-lengths 20000 --cache-rates 0.0

  uv run %(prog)s --context zz --deployment-name minimax-m27-int8-internal \
      --token-lengths 20000 80000 --cache-rates 0.0 0.8
""",
    )
    parser.add_argument("--context", default="zz", help="kubectl context alias")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE, help="target deployment namespace")
    parser.add_argument("--metrics-namespace", default=None, help="metrics namespace; defaults to --namespace")
    parser.add_argument("--deployment-name", required=True, help="target deployment/service/ingress name")
    parser.add_argument(
        "--model",
        default=None,
        help="model name for API requests; auto-detected from /v1/models if omitted",
    )
    parser.add_argument(
        "--thanos-context",
        default=None,
        help="Thanos cluster alias; defaults to --context",
    )
    parser.add_argument(
        "--thanos-query",
        action="append",
        default=[],
        help=(
            "override metric query as name=promql; can be repeated, "
            'e.g. --thanos-query gpu=avg(dcu_container_dcu_util{dcu_pod_name=~"x"})'
        ),
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
        default=DEFAULT_CONCURRENCY,
        help="concurrent requests per case",
    )
    parser.add_argument(
        "--total-requests",
        type=int,
        default=48,
        help="total requests per case (fixed mode)",
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
        "--request-timeout-seconds",
        type=int,
        default=600,
        help="per request timeout for streaming responses",
    )
    parser.add_argument(
        "--benchmark-mode",
        choices=["fixed", "sustained"],
        default=DEFAULT_BENCHMARK_MODE,
        help="fixed runs a bounded request count, sustained keeps pressure for a fixed duration",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=600,
        help="duration for sustained mode",
    )
    parser.add_argument(
        "--report-interval-seconds",
        type=int,
        default=30,
        help="live report interval for sustained mode",
    )
    parser.add_argument(
        "--output-tokens",
        type=int,
        default=DEFAULT_OUTPUT_TOKENS_PER_REQUEST,
        help="max_tokens per request",
    )
    parser.add_argument(
        "--warmup-seconds",
        type=int,
        default=10,
        help="extra wait after ingress target check passes",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="explicit chat completions URL; defaults to http://<deployment>.<cluster-domain>:58000/v1/chat/completions",
    )
    args = parser.parse_args()
    if not args.metrics_namespace:
        args.metrics_namespace = args.namespace
    args.metrics_service = args.deployment_name
    args.pods = None
    args.pod_regex = None
    return validate_common_args(parser, args)


async def orchestrate(args: argparse.Namespace):
    base_url = args.base_url
    metrics_service = args.metrics_service
    deployment = get_deployment_json(args.context, args.deployment_name, args.namespace)
    pod_regex = get_pod_regex(
        args.context,
        deployment,
        args.deployment_name,
        namespace=args.namespace,
    )
    if not base_url:
        base_url = build_public_ingress_base_url(args.context, args.deployment_name)
    if args.warmup_seconds > 0:
        print(f"    Ingress target ready, sleeping {args.warmup_seconds}s for warmup")
        time.sleep(args.warmup_seconds)
    print_benchmark_summary(
        args,
        "vLLM public-ingress benchmark",
        extra_lines=[
            f"Deployment: {args.deployment_name}",
            f"Metrics service: {metrics_service}",
            f"Pod regex: {pod_regex}",
            f"Base URL: {base_url}",
        ],
    )
    return await run_benchmark_matrix(
        args=args,
        base_url=base_url,
        metrics_service=metrics_service,
        pod_regex=pod_regex,
        result_prefix={
            "target": {
                "context": args.context,
                "namespace": args.namespace,
                "deployment_name": args.deployment_name,
                "thanos_context": args.thanos_context or args.context,
                "metrics_namespace": args.metrics_namespace,
                "metrics_service": metrics_service,
                "mode": "public-ingress",
                "base_url": base_url,
            },
            "baseline": {},
        },
    )


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
