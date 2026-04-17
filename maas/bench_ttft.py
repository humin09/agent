"""
vLLM 完整压测脚本
支持：不同输入长度、缓存命中率、Input/Output TPS、10分钟测试窗口、Thanos指标收集
"""

import asyncio
import time
import json
import statistics
import argparse
import aiohttp
import random
import sys
import os
from typing import List, Dict, Optional, Any

sys.path.insert(0, os.path.expanduser("~/k8s"))
from thanos import ThanosClient


BASE_URL = "http://localhost:18000/v1/chat/completions"
MODEL = "/models/MiniMax-M2.5-W8A8"
OUTPUT_TOKENS_PER_REQUEST = 16

FILLER_UNIT = "在一个阳光明媚的早晨，小明和他的朋友们一起去公园散步。他们看到了很多美丽的花朵和高大的树木。"
CACHE_BASE_TEXTS = {}


def init_cache_base_texts():
    global CACHE_BASE_TEXTS
    for length in [20000, 40000, 80000, 120000, 26000, 50000]:
        CACHE_BASE_TEXTS[length] = generate_fixed_input(length, seed=42)


def generate_fixed_input(target_tokens: int, seed: int = 42) -> str:
    rng = random.Random(seed)
    units_needed = target_tokens // 40
    text = ""
    for i in range(units_needed):
        variant = rng.choice(
            [
                "在一个阳光明媚的早晨",
                "在一个风和日丽的下午",
                "在一个星空灿烂的夜晚",
                "在一个细雨蒙蒙的黄昏",
            ]
        )
        text += f"{variant}，小明和他的朋友们一起去公园散步。他们看到了很多美丽的花朵和高大的树木。"
    return text


def generate_input_with_cache_rate(target_tokens: int, cache_hit_rate: float) -> str:
    available_lengths = sorted(CACHE_BASE_TEXTS.keys())
    closest_length = min(available_lengths, key=lambda x: abs(x - target_tokens))
    base_text = CACHE_BASE_TEXTS[closest_length]

    cached_tokens = int(target_tokens * cache_hit_rate)
    new_tokens = target_tokens - cached_tokens

    cached_chars = cached_tokens * 2
    cached_part = base_text[:cached_chars]

    new_part_units = new_tokens // 40
    new_part = ""
    rng = random.Random(int(time.time() * 1000) % (2**32))
    for i in range(new_part_units):
        variant = rng.choice(
            [
                "在一个风雪交加的冬日",
                "在一个秋高气爽的季节",
                "在一个春意盎然的时节",
                "在一个夏日炎炎的正午",
            ]
        )
        new_part += f"{variant}，小红和她的同学们一起去图书馆看书。她们借阅了很多有趣的书籍和杂志。"

    return cached_part + new_part


def generate_input(target_tokens: int) -> str:
    """Generate input text of approximately target_tokens length."""
    units_needed = target_tokens // 40
    text = FILLER_UNIT * units_needed
    return text


async def measure_ttft_and_e2e(
    session: aiohttp.ClientSession, input_text: str, req_id: int
) -> dict:
    """Send a streaming request and measure TTFT and E2E."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": f"请用一句话总结以下内容：\n{input_text}"}
        ],
        "max_tokens": OUTPUT_TOKENS_PER_REQUEST,
        "temperature": 0.1,
        "stream": True,
    }

    start = time.monotonic()
    ttft = None
    e2e = None
    error = None

    try:
        async with session.post(
            BASE_URL, json=payload, timeout=aiohttp.ClientTimeout(total=600)
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                return {
                    "req_id": req_id,
                    "ttft": None,
                    "e2e": None,
                    "error": f"HTTP {resp.status}: {body[:200]}",
                }

            async for line in resp.content:
                line = line.decode("utf-8").strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunk = json.loads(line[6:])
                    if ttft is None:
                        if chunk.get("choices") and chunk["choices"][0].get(
                            "delta", {}
                        ).get("content"):
                            ttft = time.monotonic() - start
                        if chunk.get("choices") and chunk["choices"][0].get(
                            "delta", {}
                        ).get("reasoning_content"):
                            ttft = time.monotonic() - start
                elif line == "data: [DONE]":
                    e2e = time.monotonic() - start
                    break

            if ttft is None:
                ttft = time.monotonic() - start
            if e2e is None:
                e2e = time.monotonic() - start

    except Exception as e:
        error = str(e)

    return {"req_id": req_id, "ttft": ttft, "e2e": e2e, "error": error}


async def run_benchmark(
    target_tokens: int,
    concurrency: int,
    total_requests: int,
    cache_hit_rate: float = 0.0,
):
    """Run benchmark for a given input length and cache hit rate."""
    init_cache_base_texts()
    print(f"\n{'=' * 60}")
    print(
        f"Input target: ~{target_tokens // 1000}K tokens | Concurrency: {concurrency} | Total: {total_requests}"
    )
    print(f"Cache Hit Rate: {int(cache_hit_rate * 100)}%")

    sem = asyncio.Semaphore(concurrency)
    results = []

    async def bounded_request(session, req_id):
        input_text = generate_input_with_cache_rate(target_tokens, cache_hit_rate)
        async with sem:
            return await measure_ttft_and_e2e(session, input_text, req_id)

    async with aiohttp.ClientSession() as session:
        tasks = [bounded_request(session, i) for i in range(total_requests)]
        start_all = time.monotonic()
        results = await asyncio.gather(*tasks)
        total_time = time.monotonic() - start_all

    ttfts = [r["ttft"] for r in results if r["ttft"] is not None]
    e2es = [r["e2e"] for r in results if r["e2e"] is not None]
    errors = [r for r in results if r["error"] is not None]

    if ttfts:
        print(f"  TTFT min:    {min(ttfts):.2f}s")
        print(f"  TTFT max:    {max(ttfts):.2f}s")
        print(f"  TTFT median: {statistics.median(ttfts):.2f}s")
        print(f"  TTFT mean:   {statistics.mean(ttfts):.2f}s")
        if len(ttfts) > 1:
            print(f"  TTFT stdev:  {statistics.stdev(ttfts):.2f}s")
    if e2es:
        print(f"  E2E min:     {min(e2es):.2f}s")
        print(f"  E2E max:     {max(e2es):.2f}s")
        print(f"  E2E median:  {statistics.median(e2es):.2f}s")
        print(f"  E2E mean:    {statistics.mean(e2es):.2f}s")
        if len(e2es) > 1:
            print(f"  E2E stdev:   {statistics.stdev(e2es):.2f}s")
    print(f"  Total time:  {total_time:.2f}s")
    if errors:
        print(f"  Errors: {len(errors)}")
        for e in errors[:3]:
            print(f"    req#{e['req_id']}: {e['error'][:100]}")

    return {
        "target_tokens": target_tokens,
        "concurrency": concurrency,
        "total_requests": total_requests,
        "cache_hit_rate": cache_hit_rate,
        "ttft_median": statistics.median(ttfts) if ttfts else None,
        "ttft_mean": statistics.mean(ttfts) if ttfts else None,
        "ttft_min": min(ttfts) if ttfts else None,
        "ttft_max": max(ttfts) if ttfts else None,
        "e2e_median": statistics.median(e2es) if e2es else None,
        "e2e_mean": statistics.mean(e2es) if e2es else None,
        "e2e_min": min(e2es) if e2es else None,
        "e2e_max": max(e2es) if e2es else None,
        "errors": len(errors),
    }


async def main():
    parser = argparse.ArgumentParser(description="vLLM TTFT + E2E Benchmark")
    parser.add_argument(
        "--tokens",
        type=int,
        nargs="+",
        default=[26000, 50000, 80000, 120000],
        help="Target token counts to test",
    )
    parser.add_argument(
        "--concurrency", type=int, default=8, help="Max concurrent requests"
    )
    parser.add_argument(
        "--total", type=int, default=16, help="Total requests per token level"
    )
    parser.add_argument(
        "--cache-rates",
        type=float,
        nargs="+",
        default=[0.0],
        help="Cache hit rates to test (0.0-1.0)",
    )
    parser.add_argument("--url", type=str, default=None, help="API endpoint URL")
    args = parser.parse_args()

    global BASE_URL
    if args.url:
        BASE_URL = args.url

    print(f"Benchmark config: concurrency={args.concurrency}, total={args.total}")
    print(f"Token levels: {args.tokens}")
    print(f"Cache rates: {[f'{int(r * 100)}%' for r in args.cache_rates]}")

    all_results = []
    for token_count in args.tokens:
        for cache_rate in args.cache_rates:
            result = await run_benchmark(
                token_count, args.concurrency, args.total, cache_rate
            )
            all_results.append(result)

    print(f"\n{'=' * 100}")
    print("Summary:")
    print(
        f"{'Tokens':>10} | {'Cache':>6} | {'Median TTFT':>12} | {'Median E2E':>12} | {'Errors':>6}"
    )
    print("-" * 110)
    for r in all_results:
        cache_pct = f"{int(r['cache_hit_rate'] * 100)}%"
        ttft_med = f"{r['ttft_median']:.2f}s" if r["ttft_median"] else "N/A"
        e2e_med = f"{r['e2e_median']:.2f}s" if r["e2e_median"] else "N/A"
        print(
            f"{r['target_tokens']:>10} | {cache_pct:>6} | {ttft_med:>12} | {e2e_med:>12} | {r['errors']:>6}"
        )


if __name__ == "__main__":
    asyncio.run(main())
