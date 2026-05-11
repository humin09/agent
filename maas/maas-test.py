#!/usr/bin/env python3
"""
Maas benchmark toolkit - Pod-based performance testing within K8s cluster.

Usage (inside ske-model-tool pod):
  python maas-test.py --service minimax-m25-int8-yy --token-lengths 20000 --cache-rates 0.0
  python maas-test.py --service minimax-m27-int8 --token-lengths 20000 80000 --cache-rates 0.0 0.8
"""

import argparse
import asyncio
import json
import os
import random
import statistics
import sys
import time
import urllib.parse
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    import requests
except ImportError:
    requests = None

DEFAULT_TOKEN_LENGTHS = [20000, 40000, 80000, 120000]
DEFAULT_CACHE_RATES = [0.0, 0.4, 0.8]
DEFAULT_RESULT_LOG = "/tmp/maas-benchmark-result.log"
DEFAULT_NAMESPACE = "ske-model"
DEFAULT_OUTPUT_TOKENS_PER_REQUEST = 256
DEFAULT_CONCURRENCY = 24
DEFAULT_BENCHMARK_MODE = "fixed"
SERVICE_PORT = 8000
VM_CLUSTER_ENDPOINTS = {
    "zz": "https://vm-cluster.zzai2.scnet.cn:58043/select/0/prometheus/api/v1",
    "ks": "https://vm-cluster.ksai.scnet.cn:58043/select/0/prometheus/api/v1",
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
class BenchmarkCase:
    token_length: int
    cache_rate: float


class CommandError(RuntimeError):
    pass


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
        "stream_options": {"include_usage": True},
    }
    start = time.monotonic()
    ttft = None
    e2e = None
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
                    "error": f"HTTP {resp.status}: {body[:200]}",
                }
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunk = json.loads(line[6:])
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = (
                        delta.get("content")
                        or delta.get("reasoning_content")
                        or delta.get("reasoning")
                    )
                    if ttft is None:
                        ttft = time.monotonic() - start
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
    ttft_summary = summarize_samples(ttfts)
    e2e_summary = summarize_samples(e2es)
    print(
        f"    Case tokens={case.token_length}, cache={case.cache_rate:.0%}, "
        f"success={len(successes)}/{len(sample_results)}"
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
            snapshot = {
                "elapsed_s": round(elapsed),
                "total": total,
                "success": stats["success_count"],
                "errors": stats["error_count"],
                "recent_avg_ttft": round(avg_ttft, 1),
                "recent_avg_e2e": round(avg_e2e, 1),
            }
            stats["timeline"].append(snapshot)
            print(
                f"  [{elapsed:6.0f}s] total={total}, success={stats['success_count']}, "
                f"errors={stats['error_count']}, "
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
    print(f"\n    End: {datetime.now().isoformat()}")
    print(f"    Wall time: {total_time:.1f}s")
    print(f"    Success: {stats['success_count']}, Errors: {stats['error_count']}")
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


def save_results(result_log: str, payload: Dict[str, Any]) -> None:
    path = Path(result_log)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n>>> Results saved to {path}")


def build_default_vm_queries(service_name: str) -> Dict[str, str]:
    """Build Prometheus queries for vm-cluster."""
    return {
        "input_tps": f'sum(rate(vllm:prompt_tokens_total{{service="{service_name}"}}[5m]))',
        "output_tps": f'sum(rate(vllm:generation_tokens_total{{service="{service_name}"}}[5m]))',
        "total_tps": (
            f'sum(rate(vllm:prompt_tokens_total{{service="{service_name}"}}[5m])) + '
            f'sum(rate(vllm:generation_tokens_total{{service="{service_name}"}}[5m]))'
        ),
        "itl_avg": (
            f'sum(rate(vllm:inter_token_latency_seconds_sum{{service="{service_name}"}}[5m])) / '
            f'clamp_min(sum(rate(vllm:inter_token_latency_seconds_count{{service="{service_name}"}}[5m])), 1e-10)'
        ),
        "prefix_cache_hit_rate_avg": (
            f"sum(rate(vllm:prefix_cache_hits_total{{service=\"{service_name}\"}}[5m])) / "
            f"clamp_min(sum(rate(vllm:prefix_cache_queries_total{{service=\"{service_name}\"}}[5m])), 1e-10)"
        ),
        "kv_cache_usage_avg": f"avg(vllm:kv_cache_usage_perc{{service=\"{service_name}\"}})",
    }


def query_vm_cluster(promql: str, start_time: float, end_time: float, step: str = "30s", endpoint: str = None) -> Dict[str, Any]:
    """Query vm-cluster via Prometheus API."""
    if not requests:
        raise CommandError("requests library not available; install it to use vm-cluster queries")

    if not endpoint:
        endpoint = VM_CLUSTER_ENDPOINTS.get("zz", VM_CLUSTER_ENDPOINTS["zz"])

    url = f"{endpoint}/query_range"
    params = {
        "query": promql,
        "start": int(start_time),
        "end": int(end_time),
        "step": step,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"    WARNING: vm-cluster query failed: {exc}")
        return {"status": "error", "error": str(exc)[:200]}


def flatten_vm_query_values(result: Dict[str, Any]) -> List[float]:
    """Extract values from vm-cluster query result."""
    if result.get("status") != "success":
        return []
    series = result.get("data", {}).get("result", [])
    values: List[float] = []
    for item in series:
        for _, raw_value in item.get("values", []):
            try:
                values.append(float(raw_value))
            except (TypeError, ValueError):
                continue
    return values


def collect_vm_metrics(
    queries: Dict[str, str],
    start_time: datetime,
    end_time: datetime,
    step: str = "30s",
    endpoint: str = None,
) -> Dict[str, Any]:
    """Collect metrics from vm-cluster."""
    metrics: Dict[str, Any] = {
        "window": {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "step": step,
        },
        "queries": queries,
        "results": {},
    }

    for name, promql in queries.items():
        result = query_vm_cluster(promql, start_time.timestamp(), end_time.timestamp(), step, endpoint=endpoint)
        if result.get("status") == "success":
            values = flatten_vm_query_values(result)
            if values:
                summary = summarize_samples(values)
                metrics["results"][name] = {
                    "promql": promql,
                    "series_count": len(result.get("data", {}).get("result", [])),
                    "sample_count": len(values),
                    "avg": summary["avg"],
                }
            else:
                metrics["results"][name] = {
                    "promql": promql,
                    "error": "query returned no samples",
                }
        else:
            metrics["results"][name] = {
                "promql": promql,
                "error": result.get("error", "unknown error"),
            }
    return metrics


async def run_benchmark_matrix(
    *,
    args: argparse.Namespace,
    base_url: str,
    service_name: str,
    vm_endpoint: str,
    result_prefix: Dict[str, Any],
) -> Dict[str, Any]:
    model = resolve_model(args, base_url)

    vm_queries = build_default_vm_queries(service_name) if requests else {}

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
            "vm_step": args.vm_step,
            "vm_trim_seconds": args.vm_trim_seconds,
            "request_timeout_seconds": args.request_timeout_seconds,
            "output_tokens": args.output_tokens,
        },
        "baseline": {
            **result_prefix.get("baseline", {}),
            "vm_queries": vm_queries,
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

            vm_metrics = {}
            if requests:
                trim_start = case_start.timestamp() + args.vm_trim_seconds
                trim_end = case_end.timestamp() - args.vm_trim_seconds
                if trim_start < trim_end:
                    vm_metrics = collect_vm_metrics(
                        vm_queries,
                        datetime.fromtimestamp(trim_start),
                        datetime.fromtimestamp(trim_end),
                        step=args.vm_step,
                        endpoint=vm_endpoint,
                    )

            all_results["results"].append(
                {
                    "case": asdict(case),
                    "start_time": case_start.isoformat(),
                    "end_time": case_end.isoformat(),
                    "benchmark": benchmark_summary,
                    "vm_metrics": vm_metrics,
                }
            )
            save_results(args.result_log, all_results)

    all_results["test_end_time"] = datetime.now().isoformat()
    save_results(args.result_log, all_results)
    return all_results


def resolve_model(args: argparse.Namespace, base_url: str) -> str:
    if args.model:
        return args.model
    return detect_model(base_url)


def print_benchmark_summary(args: argparse.Namespace, title: str, base_url: str) -> None:
    total_cases = len(args.token_lengths) * len(args.cache_rates)
    print("=" * 100)
    print(title)
    print("=" * 100)
    print(f"Service: {args.service}")
    print(f"Base URL: {base_url}")
    print(f"Model: {args.model or '(auto-detect)'}")
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark vLLM service within K8s cluster.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python maas-test.py --service minimax-m25-int8-yy \\
      --token-lengths 20000 --cache-rates 0.0

  python maas-test.py --service minimax-m27-int8 \\
      --token-lengths 20000 80000 --cache-rates 0.0 0.8
""",
    )
    parser.add_argument("--service", required=True, help="target vLLM service name (K8s DNS)")
    parser.add_argument("--model", default=None, help="model name for API requests; auto-detected if omitted")
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
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="concurrent requests per case")
    parser.add_argument("--total-requests", type=int, default=48, help="total requests per case (fixed mode)")
    parser.add_argument("--result-log", default=DEFAULT_RESULT_LOG, help="output json file")
    parser.add_argument("--vm-step", default="30s", help="step for vm-cluster query_range")
    parser.add_argument("--vm-trim-seconds", type=int, default=0, help="trim benchmark window edges before querying vm-cluster")
    parser.add_argument("--request-timeout-seconds", type=int, default=600, help="per request timeout")
    parser.add_argument(
        "--benchmark-mode",
        choices=["fixed", "sustained"],
        default=DEFAULT_BENCHMARK_MODE,
        help="fixed runs a bounded request count, sustained keeps pressure for a fixed duration",
    )
    parser.add_argument("--duration-seconds", type=int, default=600, help="duration for sustained mode")
    parser.add_argument("--report-interval-seconds", type=int, default=30, help="live report interval for sustained mode")
    parser.add_argument("--output-tokens", type=int, default=DEFAULT_OUTPUT_TOKENS_PER_REQUEST, help="max_tokens per request")
    parser.add_argument("--vm-cluster-endpoint", default=None, help="vm-cluster Prometheus API endpoint; auto-detect from cluster if not provided")

    args = parser.parse_args()
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


async def main() -> int:
    args = parse_args()
    try:
        base_url = f"http://{args.service}:{SERVICE_PORT}/v1/chat/completions"

        # 自动检测或使用指定的 vm-cluster endpoint
        if args.vm_cluster_endpoint:
            vm_endpoint = args.vm_cluster_endpoint
        else:
            cluster_context = os.environ.get("CLUSTER_CONTEXT", "zz")
            vm_endpoint = VM_CLUSTER_ENDPOINTS.get(cluster_context, VM_CLUSTER_ENDPOINTS["zz"])
            print(f"Auto-detected cluster context: {cluster_context}")

        print_benchmark_summary(args, "vLLM service benchmark (K8s cluster)", base_url)

        await run_benchmark_matrix(
            args=args,
            base_url=base_url,
            service_name=args.service,
            vm_endpoint=vm_endpoint,
            result_prefix={
                "target": {
                    "service": args.service,
                    "mode": "k8s-service",
                    "base_url": base_url,
                    "vm_cluster_endpoint": vm_endpoint,
                },
                "baseline": {},
            },
        )
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as exc:
        print(f"\nERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
