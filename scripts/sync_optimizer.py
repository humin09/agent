#!/usr/bin/env python3
"""根据 prefix 大小和链路带宽矩阵，贪心分配 owner 并生成 sync-plan.yaml。

用法：
  # 使用默认数据运行
  python ~/agent/scripts/sync_optimizer.py \
    --prefix-sizes ~/agent/reports/prefix_sizes.json \
    --bandwidth ~/agent/reports/bandwidth.json

  # 手动指定带宽（Mbps），省略测试步骤
  python ~/agent/scripts/sync_optimizer.py \
    --prefix-sizes prefix_sizes.json \
    --bandwidth-matrix '{"xa":{"ks":320,"zz":180,"qd":100,"dz":80},"ks":{"zz":200,"qd":300,"dz":120},"zz":{"ks":200,"qd":200,"dz":260},"qd":{"ks":300,"zz":200,"dz":90},"dz":{"ks":120,"zz":260,"qd":90}}'

  # 仅输出分配结果
  python ~/agent/scripts/sync_optimizer.py --prefix-sizes prefix_sizes.json --bandwidth bandwidth.json --quiet

  # 输出到文件
  python ~/agent/scripts/sync_optimizer.py --prefix-sizes prefix_sizes.json --bandwidth bandwidth.json --output sync-plan.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
import yaml
from collections import defaultdict
from typing import Dict, List, Tuple


SOURCE = "xa"
DEFAULT_CLUSTERS = ["ks", "zz", "qd", "dz"]


def load_prefix_sizes(path: str) -> List[dict]:
    with open(path) as f:
        data = json.load(f)
    return data.get("prefixes", data if isinstance(data, list) else [])


def load_bandwidth(path: str) -> Dict[str, Dict[str, float]]:
    with open(path) as f:
        data = json.load(f)
    links = data.get("links", data if isinstance(data, list) else [])
    bw: Dict[str, Dict[str, float]] = defaultdict(dict)
    for link in links:
        if "error" not in link:
            bw[link["src"]][link["dst"]] = link["bandwidth_mbps"]
    return dict(bw)


def compute_cost(
    owner: str,
    prefix_size_bytes: float,
    clusters: List[str],
    bandwidth: Dict[str, Dict[str, float]],
    owner_load: Dict[str, float],
    egress_limit_mbps: float = 0,
) -> float:
    size_mb = prefix_size_bytes / (1024 * 1024)
    bw_from_source = bandwidth.get(SOURCE, {}).get(owner, 100)
    pull_time = size_mb * 8 / bw_from_source

    max_distribute_time = 0
    for target in clusters:
        if target == owner:
            continue
        bw_owner_to_target = bandwidth.get(owner, {}).get(target, 50)
        dist_time = size_mb * 8 / bw_owner_to_target
        max_distribute_time = max(max_distribute_time, dist_time)

    existing_load = owner_load.get(owner, 0)
    load_penalty = existing_load * 8 / max(bw_from_source, 1) * 0.1

    return pull_time + max_distribute_time + load_penalty


def greedy_allocate(
    prefix_sizes: List[dict],
    clusters: List[str],
    bandwidth: Dict[str, Dict[str, float]],
) -> Dict[str, List[str]]:
    sorted_prefixes = sorted(prefix_sizes, key=lambda x: x.get("size_bytes", 0), reverse=True)
    owner_load: Dict[str, float] = defaultdict(float)
    allocation: Dict[str, List[str]] = {c: [] for c in clusters}

    for p in sorted_prefixes:
        prefix = p["prefix"]
        size_bytes = p.get("size_bytes", 0)
        if size_bytes == 0:
            min_owner = min(clusters, key=lambda c: len(allocation[c]))
            allocation[min_owner].append(prefix)
            continue

        best_owner = None
        best_cost = float("inf")
        for candidate in clusters:
            cost = compute_cost(candidate, size_bytes, clusters, bandwidth, owner_load)
            if cost < best_cost:
                best_cost = cost
                best_owner = candidate

        allocation[best_owner].append(prefix)
        owner_load[best_owner] += size_bytes

    for c in clusters:
        allocation[c].sort()

    return allocation


def generate_sync_plan(
    allocation: Dict[str, List[str]],
    clusters: List[str],
) -> dict:
    plan = {
        "source": SOURCE,
        "clusters": clusters,
        "owners": {},
        "targets": {},
    }

    for owner, prefixes in allocation.items():
        plan["owners"][owner] = prefixes

    for target in clusters:
        plan["targets"][target] = {}
        for owner in clusters:
            if owner == target:
                continue
            owned_prefixes = allocation.get(owner, [])
            if owned_prefixes:
                plan["targets"][target][owner] = owned_prefixes

    return plan


def print_summary(allocation: Dict[str, List[str]], prefix_sizes: List[dict]):
    size_map = {p["prefix"]: p.get("size_bytes", 0) for p in prefix_sizes}
    total_size = sum(size_map.values())

    print(f"\n{'owner':<8} {'prefixes':>10} {'size':>12} {'%':>6}")
    print("-" * 40)
    for owner in sorted(allocation.keys()):
        prefixes = allocation[owner]
        owner_size = sum(size_map.get(p, 0) for p in prefixes)
        pct = (owner_size / total_size * 100) if total_size > 0 else 0
        size_str = fmt_size(owner_size)
        print(f"{owner:<8} {len(prefixes):>10} {size_str:>12} {pct:>5.1f}%")
    print("-" * 40)
    print(f"{'total':<8} {sum(len(v) for v in allocation.values()):>10} {fmt_size(total_size):>12}")


def fmt_size(b: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}PiB"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prefix-sizes", required=True, help="prefix_sizes.json path")
    ap.add_argument("--bandwidth", help="bandwidth.json path")
    ap.add_argument("--bandwidth-matrix", help="inline JSON bandwidth matrix")
    ap.add_argument("--clusters", nargs="*", default=DEFAULT_CLUSTERS)
    ap.add_argument("--output", "-o", help="output sync-plan.yaml path")
    ap.add_argument("--quiet", action="store_true", help="only output allocation")
    args = ap.parse_args()

    prefix_sizes = load_prefix_sizes(args.prefix_sizes)
    if not prefix_sizes:
        print("ERROR: no prefix size data", file=sys.stderr)
        return 1

    if args.bandwidth_matrix:
        bandwidth = json.loads(args.bandwidth_matrix)
    elif args.bandwidth:
        bandwidth = load_bandwidth(args.bandwidth)
    else:
        print("WARNING: no bandwidth data, using defaults", file=sys.stderr)
        bandwidth = {
            SOURCE: {c: 100 for c in args.clusters},
        }
        for c in args.clusters:
            bandwidth[c] = {other: 100 for other in args.clusters if other != c}

    allocation = greedy_allocate(prefix_sizes, args.clusters, bandwidth)

    if not args.quiet:
        print_summary(allocation, prefix_sizes)

    plan = generate_sync_plan(allocation, args.clusters)

    if args.output:
        with open(args.output, "w") as f:
            yaml.dump(plan, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"\n已保存到: {args.output}", file=sys.stderr)
    else:
        print("\n" + yaml.dump(plan, default_flow_style=False, allow_unicode=True, sort_keys=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
