#!/usr/bin/env python3
"""
各集群 MinIO 同步进度检查：以 xa（源）为基准，对比各集群每个桶的 object count。

数据源：
  - xa / sz / wh：本地 mc 统计（无 VM）
  - ks / zz / dz / qd：VictoriaMetrics 查 minio_bucket_usage_object_total
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests

requests.packages.urllib3.disable_warnings()

SOURCE_CLUSTER = "xa"
BUCKET = "gitlab-lfs-prod"

VM_CLUSTERS = {
    "ks": "https://vm.ksai.scnet.cn:58043/select/0/prometheus",
    "dz": "https://vm.dzai.scnet.cn:58043/select/0/prometheus",
    "zz": "https://vm.zzai.scnet.cn:58043/select/0/prometheus",
    "qd": "https://vm.qdai.scnet.cn:58043/select/0/prometheus",
}

MC_ONLY_CLUSTERS = ["xa", "sz", "wh"]

DEFAULT_CLUSTERS = [SOURCE_CLUSTER] + [c for c in VM_CLUSTERS] + ["sz", "wh"]
DEFAULT_CLUSTERS = [SOURCE_CLUSTER, "ks", "zz", "dz", "qd", "sz", "wh"]

IGNORE_BUCKETS = {"loki", "prom", "tmp", "k8s"}


def should_ignore_bucket(bucket: str) -> bool:
    return bucket in IGNORE_BUCKETS or bucket.startswith("k8s")


# ── mc 方式（无 VM 集群）───────────────────────────
def mc_bucket_objects(alias: str, bucket: str, timeout: int = 120) -> Optional[int]:
    """通过 mc stat 获取桶内对象数（比 mc ls --summarize 准确）。"""
    try:
        p = subprocess.run(
            ["mc", "stat", f"{alias}/{bucket}"],
            capture_output=True, text=True, timeout=timeout,
        )
        if p.returncode != 0:
            print(f"[{alias}/{bucket}] mc stat 失败: {p.stderr.strip()}", file=sys.stderr)
            return None
        import re
        m = re.search(r"Objects count\s*:\s*([\d,]+)", p.stdout)
        if m:
            return int(m.group(1).replace(",", ""))
        return None
    except subprocess.TimeoutExpired:
        print(f"[{alias}/{bucket}] mc stat 超时({timeout}s)", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[{alias}/{bucket}] mc stat 异常: {e}", file=sys.stderr)
        return None


def mc_bucket_size(alias: str, bucket: str, timeout: int = 120) -> Optional[int]:
    """通过 mc stat 获取桶大小（字节）。"""
    try:
        p = subprocess.run(
            ["mc", "stat", f"{alias}/{bucket}"],
            capture_output=True, text=True, timeout=timeout,
        )
        if p.returncode != 0:
            return None
        import re
        m = re.search(r"Total size\s*:\s*([\d.]+)\s*([A-Za-z]*)", p.stdout)
        if m:
            val = float(m.group(1))
            unit = m.group(2).upper()
            units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4, "TIB": 1024**4, "GIB": 1024**3}
            return int(val * units.get(unit, 1))
        return None
    except Exception as e:
        print(f"[{alias}/{bucket}] mc stat size 异常: {e}", file=sys.stderr)
        return None


# ── VM 方式（有指标集群）───────────────────────────
def vm_bucket_objects(cluster: str) -> dict[str, int]:
    """从 VM 获取所有非系统桶的对象数。"""
    base_url = VM_CLUSTERS[cluster].rstrip("/")
    try:
        params = {
            "query": f'minio_bucket_usage_object_total{{bucket=~".*"}}',
            "time": time.time(),
            "dedup": "true",
            "partial_response": "true",
        }
        resp = requests.get(f"{base_url}/api/v1/query", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[{cluster}] VM 查询失败: {e}", file=sys.stderr)
        return {}

    result = {}
    for item in data.get("data", {}).get("result", []):
        bucket = item.get("metric", {}).get("bucket", "unknown")
        if should_ignore_bucket(bucket):
            continue
        try:
            val = int(float(item.get("value", [0, "0"])[1]))
            result[bucket] = val
        except (ValueError, IndexError):
            pass
    return result


# ── 汇总 ────────────────────────────────────────────
def fetch_cluster_data(cluster: str, bucket: str) -> tuple[str, dict[str, int]]:
    """返回 (cluster, {bucket: obj_count})"""
    if cluster in VM_CLUSTERS:
        return cluster, vm_bucket_objects(cluster)
    elif cluster in MC_ONLY_CLUSTERS:
        objs = mc_bucket_objects(cluster, bucket, timeout=180)
        return cluster, {bucket: objs if objs is not None else -1}
    else:
        return cluster, {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "-c", "--clusters", nargs="*", default=DEFAULT_CLUSTERS,
        help=f"集群列表，默认：{' '.join(DEFAULT_CLUSTERS)}",
    )
    ap.add_argument(
        "--bucket", "-b", default=BUCKET,
        help=f"目标桶名，默认 {BUCKET}",
    )
    ap.add_argument(
        "--timeout", type=int, default=180,
        help="mc ls 超时秒数（默认 180）",
    )
    args = ap.parse_args()

    bucket = args.bucket
    clusters = args.clusters

    if SOURCE_CLUSTER not in clusters:
        clusters = [SOURCE_CLUSTER] + [c for c in clusters if c != SOURCE_CLUSTER]

    print(f"⏳ 采集各集群 MinIO 桶对象数（源：{SOURCE_CLUSTER}）...", file=sys.stderr)
    print(f"   目标桶：{bucket}", file=sys.stderr)
    print(f"   集群列表：{', '.join(clusters)}", file=sys.stderr)

    results = {}
    with ThreadPoolExecutor(max_workers=min(len(clusters), 6)) as executor:
        futures = {executor.submit(fetch_cluster_data, c, bucket): c for c in clusters}
        for fut in as_completed(futures):
            c, data = fut.result()
            results[c] = data

    # 源桶对象数
    xa_objs = results.get(SOURCE_CLUSTER, {}).get(bucket, 0)
    if isinstance(xa_objs, str) or xa_objs < 0:
        xa_objs = 0

    print(f"\n# MinIO 同步进度检查（基准：{SOURCE_CLUSTER}）")
    print(f"*{time.strftime('%Y-%m-%d %H:%M:%S')}*\n")
    print(f"**桶：`{bucket}`**  |  源对象数（{SOURCE_CLUSTER}）：{xa_objs:,} objects\n")

    cols = []
    for c in clusters:
        if c == SOURCE_CLUSTER:
            continue
        cols.append(c.upper())

    header = "| 集群 | 对象数 | 进度 | 差距 |"
    sep = "|------|--------|------|------|"
    print(header)
    print(sep)
    print(f"| **{SOURCE_CLUSTER.upper()}（源）** | {xa_objs:,} | 100% | - |")

    for c in clusters:
        if c == SOURCE_CLUSTER:
            continue
        objs = results.get(c, {}).get(bucket, None)
        if objs is None or objs < 0 or isinstance(objs, str):
            print(f"| **{c.upper()}** | ❓ 获取失败 | - | - |")
            continue
        diff = xa_objs - objs if xa_objs > 0 else 0
        pct = (objs / xa_objs * 100) if xa_objs > 0 else 0
        status = "✅" if diff <= 0 else ("🟡" if pct >= 99.9 else "⌛️")
        gap = f"-{diff:,}" if diff > 0 else "✅ 对齐"
        print(f"| **{c.upper()}** | {objs:,} | {pct:.2f}% | {gap} |")

    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
