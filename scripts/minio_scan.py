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
STATE_PREFIX = "local/tmp/mc-sync-state/gitlab-lfs-prod"

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


def vm_bucket_bytes(cluster: str) -> dict[str, int]:
    """从 VM 获取所有非系统桶的字节数。"""
    base_url = VM_CLUSTERS[cluster].rstrip("/")
    try:
        params = {
            "query": f'minio_bucket_usage_total_bytes{{bucket=~".*"}}',
            "time": time.time(),
            "dedup": "true",
            "partial_response": "true",
        }
        resp = requests.get(f"{base_url}/api/v1/query", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[{cluster}] VM size 查询失败: {e}", file=sys.stderr)
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


def vm_bucket_bytes_rate(cluster: str, window: str = "3h") -> Optional[dict[str, float]]:
    """从 VM 获取指定桶在 window 内的平均写入速率（bytes/sec），用 increase / window 估算。"""
    if cluster not in VM_CLUSTERS:
        return None
    base_url = VM_CLUSTERS[cluster].rstrip("/")
    try:
        params = {
            "query": f'increase(minio_bucket_usage_total_bytes{{bucket=~".*"}}[{window}])',
            "time": time.time(),
            "dedup": "true",
            "partial_response": "true",
        }
        resp = requests.get(f"{base_url}/api/v1/query", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return None

    result = {}
    window_sec_map = {"15m": 900, "1h": 3600, "3h": 10800, "6h": 21600, "1d": 86400, "7d": 604800}
    window_sec = window_sec_map.get(window, 10800)
    for item in data.get("data", {}).get("result", []):
        bucket = item.get("metric", {}).get("bucket", "unknown")
        if should_ignore_bucket(bucket):
            continue
        try:
            val = float(item.get("value", [0, "0"])[1])
            bps = val / window_sec if val > 0 else 0.0
            result[bucket] = max(result.get(bucket, 0.0), bps)
        except (ValueError, IndexError):
            pass
    return result


# ── 读取 MinIO state 文件 ────────────────────────────
def mc_read_sync_state(cluster: str, bucket: str) -> dict[str, int]:
    """
    从 local/tmp/mc-sync-state/<bucket>/ 读取所有 shard 的 JSON，
    返回 {"shard-0": 1234, "shard-1": 5678}
    """
    state_path = f"{STATE_PREFIX}/{bucket}"
    try:
        p = subprocess.run(
            ["mc", "ls", "--json", state_path],
            capture_output=True, text=True, timeout=60,
        )
        if p.returncode != 0:
            return {}

        result = {}
        for line in p.stdout.splitlines():
            try:
                item = json.loads(line)
                if item.get("type") != "file":
                    continue
                key = item.get("key", "")
                if not key.endswith(".json"):
                    continue
                shard_name = key.rsplit("/", 1)[-1].replace(".json", "")
                r = subprocess.run(
                    ["mc", "cat", f"{state_path}/{key}"],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    result[shard_name] = data.get("count", len(data.get("synced", [])))
            except (json.JSONDecodeError, KeyError):
                continue
        return result
    except subprocess.TimeoutExpired:
        print(f"[{cluster}] mc ls state 超时", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"[{cluster}] 读取 sync state 失败: {e}", file=sys.stderr)
        return {}


# ── 汇总 ────────────────────────────────────────────
def fetch_cluster_data(cluster: str, bucket: str) -> tuple[str, dict[str, int], dict[str, int], Optional[float], dict[str, int]]:
    """返回 (cluster, {bucket: obj_count}, {bucket: bytes}, bandwidth_bps, {shard: synced_count})"""
    if cluster in VM_CLUSTERS:
        bucket_objs = vm_bucket_objects(cluster)
        bucket_bytes = vm_bucket_bytes(cluster)
        bps_map = vm_bucket_bytes_rate(cluster, window="3h")
        bps = bps_map.get(bucket) if bps_map else None
        sync_state = mc_read_sync_state(cluster, bucket)
        return cluster, bucket_objs, bucket_bytes, bps, sync_state
    elif cluster in MC_ONLY_CLUSTERS:
        objs = mc_bucket_objects(cluster, bucket, timeout=180)
        sz = mc_bucket_size(cluster, bucket, timeout=180)
        return cluster, {bucket: objs if objs is not None else -1}, {bucket: sz if sz is not None else -1}, None, {}
    else:
        return cluster, {}, {}, None, {}


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

    print(f"⏳ 采集各集群 MinIO 桶对象数和同步状态（源：{SOURCE_CLUSTER}）...", file=sys.stderr)
    print(f"   目标桶：{bucket}", file=sys.stderr)
    print(f"   集群列表：{', '.join(clusters)}", file=sys.stderr)

    results = {}
    sizes = {}
    bws = {}
    sync_states = {}
    with ThreadPoolExecutor(max_workers=min(len(clusters), 6)) as executor:
        futures = {executor.submit(fetch_cluster_data, c, bucket): c for c in clusters}
        for fut in as_completed(futures):
            c, data, data_bytes, bps, state = fut.result()
            results[c] = data
            sizes[c] = data_bytes
            bws[c] = bps
            sync_states[c] = state

    # 源桶对象数/字节
    xa_objs = results.get(SOURCE_CLUSTER, {}).get(bucket, 0)
    xa_bytes = sizes.get(SOURCE_CLUSTER, {}).get(bucket, 0)
    if isinstance(xa_objs, str) or xa_objs < 0:
        xa_objs = 0
    if xa_bytes < 0:
        xa_bytes = 0

    def _fmt_bytes(b):
        if b is None or b < 0:
            return "-"
        gb = b / (1024 ** 3)
        if gb >= 1024:
            return f"{gb / 1024:.2f} TB"
        return f"{gb:.2f} GB"

    def _fmt_bps(bps):
        if bps is None or bps <= 0:
            return "-"
        mb_s = bps / (1024 ** 2)
        gb_h = bps * 3600 / (1024 ** 3)
        return f"{mb_s:.1f} MB/s ({gb_h:.1f} GB/h)"

    xa_size_str = _fmt_bytes(xa_bytes) if xa_bytes else "-"
    print(f"\n# MinIO 同步进度检查（基准：{SOURCE_CLUSTER}）")
    print(f"*{time.strftime('%Y-%m-%d %H:%M:%S')}*\n")
    print(f"**桶：`{bucket}`**  |  源对象数（{SOURCE_CLUSTER}）：{xa_objs:,} objects  |  源容量：{xa_size_str}\n")

    header = "| 集群 | 对象数 | 进度 | 差距 | 容量 | 待同步 | 带宽 | sync state |"
    sep    = "|------|--------|------|------|------|--------|------|------------|"
    print(header)
    print(sep)
    print(f"| **{SOURCE_CLUSTER.upper()}（源）** | {xa_objs:,} | 100% | - | {xa_size_str} | - | - | - |")

    for c in clusters:
        if c == SOURCE_CLUSTER:
            continue
        objs = results.get(c, {}).get(bucket, None)
        b = sizes.get(c, {}).get(bucket, None)
        bps = bws.get(c)
        state = sync_states.get(c, {})

        if objs is None or objs < 0 or isinstance(objs, str):
            state_str = str(sum(state.values())) if state else "无"
            print(f"| **{c.upper()}** | ❓ 获取失败 | - | - | - | - | - | synced: {state_str} |")
            continue

        diff = xa_objs - objs if xa_objs > 0 else 0
        pct = (objs / xa_objs * 100) if xa_objs > 0 else 0

        size_str = _fmt_bytes(b)
        if xa_bytes and objs and xa_objs > 0:
            pending_bytes = max(0, xa_bytes - b) if b else xa_bytes
            pending_str = _fmt_bytes(pending_bytes)
        else:
            pending_str = "-"

        bps_str = _fmt_bps(bps)

        if state:
            total_synced = sum(state.values())
            state_parts = [f"{k}={v}" for k, v in sorted(state.items())]
            state_str = f"{total_synced:,} ({', '.join(state_parts)})"
        else:
            state_str = "无"

        gap = f"-{diff:,}" if diff > 0 else "✅ 对齐"
        print(f"| **{c.upper()}** | {objs:,} | {pct:.2f}% | {gap} | {size_str} | {pending_str} | {bps_str} | {state_str} |")

    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
