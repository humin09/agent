#!/usr/bin/env python3
"""测试集群间 MinIO 链路带宽。

通过 mc cp 在集群 alias 间拷贝测试文件并计时，计算有效带宽。

用法：
  # 从本地测试所有集群对（默认 100MB 测试文件）
  python ~/agent/scripts/bandwidth_test.py

  # 指定测试文件大小
  python ~/agent/scripts/bandwidth_test.py --size 500

  # 仅测试特定链路
  python ~/agent/scripts/bandwidth_test.py --pairs xa-ks xa-zz ks-zz

  # 从 Pod 内测试（更准确，走集群网络）
  python ~/agent/scripts/bandwidth_test.py --from-pod ks

  # 输出 JSON
  python ~/agent/scripts/bandwidth_test.py --json

  # 保存到文件
  python ~/agent/scripts/bandwidth_test.py --output bandwidth.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from itertools import permutations


CLUSTERS = ["xa", "ks", "zz", "qd", "dz"]
DEFAULT_TEST_SIZE_MB = 100
TEST_BUCKET = "tmp"
MC_TIMEOUT = 600


def generate_test_file_on(alias: str, size_mb: int) -> str:
    test_key = f"bandwidth-test/{int(time.time())}-{alias}.bin"
    cmd = [
        "mc", "cp", "/dev/urandom",
        f"{alias}/{TEST_BUCKET}/{test_key}",
    ]
    dd_cmd = [
        "sh", "-c",
        f"dd if=/dev/urandom bs=1M count={size_mb} 2>/dev/null | "
        f"mc pipe {alias}/{TEST_BUCKET}/{test_key}",
    ]
    try:
        subprocess.run(dd_cmd, capture_output=True, text=True, timeout=120)
        return test_key
    except Exception:
        return ""


def cleanup_test_file(alias: str, test_key: str):
    try:
        subprocess.run(
            ["mc", "rm", f"{alias}/{TEST_BUCKET}/{test_key}"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass


def measure_bandwidth(src: str, dst: str, test_key: str, size_mb: int) -> dict:
    src_path = f"{src}/{TEST_BUCKET}/{test_key}"
    dst_key = f"bandwidth-test/{int(time.time())}-{src}-to-{dst}.bin"
    dst_path = f"{dst}/{TEST_BUCKET}/{dst_key}"

    start = time.time()
    try:
        result = subprocess.run(
            ["mc", "cp", src_path, dst_path],
            capture_output=True, text=True, timeout=MC_TIMEOUT,
        )
        elapsed = time.time() - start
        if result.returncode == 0 and elapsed > 0:
            size_bytes = size_mb * 1024 * 1024
            bandwidth_mbps = (size_bytes * 8) / elapsed / (1024 * 1024)
            throughput_mbs = size_bytes / elapsed / (1024 * 1024)
            cleanup_test_file(dst, dst_key)
            return {
                "src": src, "dst": dst,
                "size_mb": size_mb,
                "elapsed_seconds": round(elapsed, 2),
                "bandwidth_mbps": round(bandwidth_mbps, 2),
                "throughput_mbs": round(throughput_mbs, 2),
            }
        else:
            return {
                "src": src, "dst": dst,
                "size_mb": size_mb,
                "error": result.stderr.strip()[:200] if result.stderr else f"exit_code={result.returncode}",
            }
    except subprocess.TimeoutExpired:
        return {"src": src, "dst": dst, "size_mb": size_mb, "error": f"timeout after {MC_TIMEOUT}s"}
    except Exception as e:
        return {"src": src, "dst": dst, "size_mb": size_mb, "error": str(e)}


def run_from_pod_test(ctx: str, clusters: list[str], size_mb: int) -> list[dict]:
    from_pod_results = []
    pod_cmd = [
        "kubectl", "--context", ctx, "-n", "ske",
        "get", "pod", "-l", "app=mc-client",
        "-o", "jsonpath={.items[0].metadata.name}",
    ]
    r = subprocess.run(pod_cmd, capture_output=True, text=True, timeout=15)
    if r.returncode != 0 or not r.stdout.strip():
        print(f"[{ctx}] 未找到 mc-client pod", file=sys.stderr)
        return from_pod_results

    pod = r.stdout.strip()
    print(f"[{ctx}] 使用 pod: {pod}", file=sys.stderr)

    test_key = f"bandwidth-test/{int(time.time())}-pod-test.bin"
    dd_in_pod = (
        f"dd if=/dev/urandom bs=1M count={size_mb} 2>/dev/null | "
        f"mc pipe local/{TEST_BUCKET}/{test_key}"
    )
    subprocess.run(
        ["kubectl", "--context", ctx, "-n", "ske", "exec", pod, "--", "sh", "-c", dd_in_pod],
        capture_output=True, text=True, timeout=120,
    )

    for dst in clusters:
        if dst == ctx:
            continue
        dst_path = f"{dst}/{TEST_BUCKET}/bandwidth-test/{ctx}-to-{dst}-{int(time.time())}.bin"
        src_path = f"local/{TEST_BUCKET}/{test_key}"
        exec_cmd = (
            f"{{ time mc cp {src_path} {dst_path} 2>&1 ; }} 2>&1 | "
            f"grep -E 'real|Object'"
        )
        r = subprocess.run(
            ["kubectl", "--context", ctx, "-n", "ske", "exec", pod, "--", "sh", "-c", exec_cmd],
            capture_output=True, text=True, timeout=MC_TIMEOUT,
        )
        real_match = re.search(r"real\s+(\d+)m([\d.]+)s", r.stdout)
        if not real_match:
            real_match = re.search(r"real\s+([\d.]+)s", r.stdout)
        
        if real_match:
            if "m" in real_match.group(0) and len(real_match.groups()) == 2:
                elapsed = int(real_match.group(1)) * 60 + float(real_match.group(2))
            else:
                elapsed = float(real_match.group(1))
            
            if elapsed > 0:
                size_bytes = size_mb * 1024 * 1024
                bw = (size_bytes * 8) / elapsed / (1024 * 1024)
                tp = size_bytes / elapsed / (1024 * 1024)
                from_pod_results.append({
                    "src": ctx, "dst": dst,
                    "size_mb": size_mb,
                    "elapsed_seconds": round(elapsed, 2),
                    "bandwidth_mbps": round(bw, 2),
                    "throughput_mbs": round(tp, 2),
                    "via": "pod",
                })
                print(f"  {ctx} -> {dst}: {bw:.1f} Mbps ({tp:.1f} MB/s, {elapsed:.1f}s)", file=sys.stderr)
            else:
                from_pod_results.append({"src": ctx, "dst": dst, "error": "elapsed=0"})
        else:
            from_pod_results.append({
                "src": ctx, "dst": dst,
                "error": f"no timing in output: {r.stdout[:100]}",
            })

    subprocess.run(
        ["kubectl", "--context", ctx, "-n", "ske", "exec", pod, "--",
         "mc", "rm", f"local/{TEST_BUCKET}/{test_key}"],
        capture_output=True, text=True, timeout=30,
    )
    return from_pod_results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clusters", nargs="*", default=CLUSTERS, help=f"clusters (default: {' '.join(CLUSTERS)})")
    ap.add_argument("--size", type=int, default=DEFAULT_TEST_SIZE_MB, help=f"test file size MB (default: {DEFAULT_TEST_SIZE_MB})")
    ap.add_argument("--pairs", nargs="*", help="specific pairs like xa-ks xa-zz")
    ap.add_argument("--from-pod", nargs="*", help="run from pod in these contexts (more accurate)")
    ap.add_argument("--json", action="store_true", dest="output_json", help="output JSON")
    ap.add_argument("--output", "-o", help="save JSON to file")
    args = ap.parse_args()

    clusters = args.clusters
    results = []

    if args.from_pod:
        print(f"从 Pod 内测试 (集群网络): {args.from_pod}", file=sys.stderr)
        for ctx in args.from_pod:
            print(f"\n--- {ctx} pod ---", file=sys.stderr)
            pod_results = run_from_pod_test(ctx, clusters, args.size)
            results.extend(pod_results)
    else:
        if args.pairs:
            pairs = []
            for p in args.pairs:
                parts = p.split("-")
                if len(parts) == 2:
                    pairs.append((parts[0], parts[1]))
        else:
            pairs = [(a, b) for a, b in permutations(clusters, 2)]

        print(f"测试 {len(pairs)} 条链路，测试文件 {args.size}MB...", file=sys.stderr)

        for src in clusters:
            print(f"\n准备 {src} 测试文件...", file=sys.stderr)
            test_key = generate_test_file_on(src, args.size)
            if not test_key:
                print(f"  {src}: 创建测试文件失败", file=sys.stderr)
                continue

            src_pairs = [(s, d) for s, d in pairs if s == src]
            for s, d in src_pairs:
                print(f"  {s} -> {d}...", end="", file=sys.stderr, flush=True)
                r = measure_bandwidth(s, d, test_key, args.size)
                results.append(r)
                if "error" in r:
                    print(f" ERROR: {r['error'][:60]}", file=sys.stderr)
                else:
                    print(f" {r['bandwidth_mbps']:.1f} Mbps ({r['throughput_mbs']:.1f} MB/s, {r['elapsed_seconds']:.1f}s)", file=sys.stderr)

            cleanup_test_file(src, test_key)

    data = {
        "test_size_mb": args.size,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "links": results,
    }

    if args.output:
        with open(args.output, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n已保存到: {args.output}", file=sys.stderr)

    if args.output_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'src':<6} {'dst':<6} {'MB':>5} {'秒':>7} {'Mbps':>10} {'MB/s':>8} {'状态':<20}")
        print("-" * 70)
        for r in results:
            if "error" in r:
                print(f"{r['src']:<6} {r['dst']:<6} {r['size_mb']:>5} {'-':>7} {'-':>10} {'-':>8} ERR: {r['error'][:30]}")
            else:
                print(f"{r['src']:<6} {r['dst']:<6} {r['size_mb']:>5} {r['elapsed_seconds']:>7.1f} {r['bandwidth_mbps']:>10.1f} {r['throughput_mbs']:>8.1f} OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
