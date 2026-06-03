#!/usr/bin/env python3
"""统计 gitlab-lfs-prod 桶 256 个一级 prefix (00-ff) 的大小和对象数。

用法：
  python ~/agent/scripts/prefix_size.py                    # 默认统计，输出表格
  python ~/agent/scripts/prefix_size.py --json             # 输出 JSON
  python ~/agent/scripts/prefix_size.py --alias xa         # 指定 mc alias
  python ~/agent/scripts/prefix_size.py --workers 32       # 并发数
  python ~/agent/scripts/prefix_size.py --output prefix_sizes.json  # 保存 JSON 文件
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


DEFAULT_ALIAS = "xa"
DEFAULT_BUCKET = "gitlab-lfs-prod"
DEFAULT_WORKERS = 16
MC_TIMEOUT = 120

UNIT_MULTIPLIERS = {
    "B": 1,
    "KiB": 1024,
    "MiB": 1024 ** 2,
    "GiB": 1024 ** 3,
    "TiB": 1024 ** 4,
    "PiB": 1024 ** 5,
    "KB": 1000,
    "MB": 1000 ** 2,
    "GB": 1000 ** 3,
    "TB": 1000 ** 4,
}


def parse_size(s: str) -> float:
    s = s.strip()
    m = re.match(r"([\d.]+)\s*([A-Za-z]+)", s)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2)
    return val * UNIT_MULTIPLIERS.get(unit, 1)


def measure_prefix(alias: str, bucket: str, prefix: str) -> dict:
    try:
        result = subprocess.run(
            ["mc", "du", f"{alias}/{bucket}/{prefix}/", "--depth", "0"],
            capture_output=True, text=True, timeout=MC_TIMEOUT,
        )
        if result.returncode != 0:
            if "does not exist" in result.stderr.lower() or "no such" in result.stderr.lower():
                return {"prefix": prefix, "size_bytes": 0, "object_count": 0}
            return {"prefix": prefix, "size_bytes": 0, "object_count": 0, "error": result.stderr.strip()}

        line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        parts = line.split("\t")
        if len(parts) >= 2:
            size_bytes = parse_size(parts[0])
            count_match = re.search(r"(\d+)", parts[1])
            object_count = int(count_match.group(1)) if count_match else 0
            return {"prefix": prefix, "size_bytes": size_bytes, "object_count": object_count}
        return {"prefix": prefix, "size_bytes": 0, "object_count": 0, "error": f"unparsed: {line}"}
    except subprocess.TimeoutExpired:
        return {"prefix": prefix, "size_bytes": 0, "object_count": 0, "error": "timeout"}
    except Exception as e:
        return {"prefix": prefix, "size_bytes": 0, "object_count": 0, "error": str(e)}


def fmt_size(b: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}PiB"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--alias", default=DEFAULT_ALIAS, help=f"mc alias (default: {DEFAULT_ALIAS})")
    ap.add_argument("--bucket", default=DEFAULT_BUCKET, help=f"bucket name (default: {DEFAULT_BUCKET})")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help=f"parallel workers (default: {DEFAULT_WORKERS})")
    ap.add_argument("--json", action="store_true", dest="output_json", help="output JSON")
    ap.add_argument("--output", "-o", help="save JSON to file")
    args = ap.parse_args()

    prefixes = [f"{i:02x}" for i in range(256)]
    print(f"统计 {args.alias}/{args.bucket} 的 {len(prefixes)} 个一级 prefix...", file=sys.stderr)
    start = time.time()

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(measure_prefix, args.alias, args.bucket, p): p for p in prefixes}
        done_count = 0
        for future in as_completed(futures):
            done_count += 1
            r = future.result()
            results.append(r)
            if done_count % 32 == 0 or done_count == len(prefixes):
                print(f"  进度: {done_count}/{len(prefixes)}", file=sys.stderr)

    results.sort(key=lambda x: x["size_bytes"], reverse=True)
    total_size = sum(r["size_bytes"] for r in results)
    total_objects = sum(r["object_count"] for r in results)
    elapsed = time.time() - start

    data = {
        "alias": args.alias,
        "bucket": args.bucket,
        "total_size_bytes": total_size,
        "total_objects": total_objects,
        "prefix_count": len(prefixes),
        "non_empty_count": sum(1 for r in results if r["size_bytes"] > 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "prefixes": results,
    }

    if args.output:
        with open(args.output, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"已保存到: {args.output}", file=sys.stderr)

    if args.output_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'prefix':<8} {'size':>12} {'objects':>10} {'%':>6}")
        print("-" * 40)
        for r in results:
            pct = (r["size_bytes"] / total_size * 100) if total_size > 0 else 0
            print(f"{r['prefix']:<8} {fmt_size(r['size_bytes']):>12} {r['object_count']:>10} {pct:>5.1f}%")
        print("-" * 40)
        print(f"{'total':<8} {fmt_size(total_size):>12} {total_objects:>10}")
        print(f"\n非空 prefix: {data['non_empty_count']}/{len(prefixes)}")
        print(f"耗时: {elapsed:.1f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
