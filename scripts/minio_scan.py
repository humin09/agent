#!/usr/bin/env python3
"""各集群 MinIO 桶状态检查

数据源：
  - VictoriaMetrics 指标 (ks, dz, qd, ly, zz)
  - mc stat (xa，VM 外网不可达)

输出各集群桶的对象数、容量、写入速率、读取速率。
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests

requests.packages.urllib3.disable_warnings()

BUCKET = "gitlab-lfs-prod"

VM_ENDPOINTS = {
    "xa": "http://vm.xaai.scnet.cn:58043/select/0/prometheus",
    "ks": "https://vm.ksai.scnet.cn:58043/select/0/prometheus",
    "dz": "https://vm.dzai.scnet.cn:58043/select/0/prometheus",
    "qd": "https://vm.qdai.scnet.cn:58043/select/0/prometheus",
    "ly": "https://vm.zzai.scnet.cn:58043/select/0/prometheus",
    "zz": "https://vm.zzai.scnet.cn:58043/select/0/prometheus",
}

DEFAULT_CLUSTERS = list(VM_ENDPOINTS.keys())


def _fmt_bytes(b: Optional[int]) -> str:
    if b is None or b < 0:
        return "-"
    tb = b / (1024 ** 4)
    if tb >= 1:
        return f"{tb:.2f} TiB"
    gb = b / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.2f} GiB"
    mb = b / (1024 ** 2)
    return f"{mb:.1f} MiB"


def _fmt_bps(bps: Optional[float]) -> str:
    if bps is None:
        return "-"
    if bps == 0.0:
        return "0 B/s"
    mb_s = bps / (1024 ** 2)
    tb_h = bps * 3600 / (1024 ** 4)
    if tb_h >= 0.01:
        return f"{mb_s:.1f} MB/s ({tb_h:.2f} TiB/h)"
    if mb_s >= 1:
        return f"{mb_s:.1f} MB/s"
    kb_s = bps / 1024
    return f"{kb_s:.0f} KB/s"


def _fmt_objs(n: Optional[int]) -> str:
    return f"{n:,}" if n is not None and n >= 0 else "-"


# ── VM ──────────────────────────────────────────────
def vm_query(cluster: str, query: str) -> list[dict]:
    base_url = VM_ENDPOINTS[cluster].rstrip("/")
    try:
        resp = requests.get(
            f"{base_url}/api/v1/query",
            params={"query": query, "time": time.time(),
                    "dedup": "true", "partial_response": "true"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("result", [])
    except Exception as e:
        print(f"[{cluster}] VM query 失败: {e}", file=sys.stderr)
        return []


def vm_bucket_usage(cluster: str, bucket: str) -> tuple[Optional[int], Optional[int]]:
    objs_r = vm_query(cluster, f'minio_bucket_usage_object_total{{bucket="{bucket}"}}')
    bytes_r = vm_query(cluster, f'minio_bucket_usage_total_bytes{{bucket="{bucket}"}}')
    objs = byt = None
    for r in objs_r:
        try:
            objs = max(objs or 0, int(float(r["value"][1])))
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    for r in bytes_r:
        try:
            byt = max(byt or 0, int(float(r["value"][1])))
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    return objs, byt


def vm_increase_rate(cluster: str, bucket: str, window: str = "6h") -> Optional[float]:
    results = vm_query(
        cluster, f'increase(minio_bucket_usage_total_bytes{{bucket="{bucket}"}}[{window}])',
    )
    ws = {"15m": 900, "1h": 3600, "3h": 10800, "6h": 21600, "1d": 86400}.get(window, 3600)
    best: Optional[float] = None
    for r in results:
        try:
            v = float(r["value"][1])
            bps = v / ws if v > 0 else 0.0
            best = bps if best is None else max(best, bps)
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    return best


def vm_traffic_rate(cluster: str, bucket: str, window: str = "6h") -> Optional[float]:
    results = vm_query(
        cluster, f'rate(minio_bucket_traffic_sent_bytes{{bucket="{bucket}"}}[{window}])',
    )
    total = 0.0
    for r in results:
        try:
            total += max(0, float(r["value"][1]))
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    return total if total > 0 else None


# ── 采集 ─────────────────────────────────────────────
def fetch_cluster(cluster: str) -> dict:
    info: dict = {"cluster": cluster}
    objs, byt = vm_bucket_usage(cluster, BUCKET)
    write_rate = vm_increase_rate(cluster, BUCKET, "6h")
    read_rate = vm_traffic_rate(cluster, BUCKET, "6h")
    info.update(objects=objs, bytes=byt, write_rate=write_rate, read_rate=read_rate)
    return info


# ── 主流程 ────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-c", "--clusters", nargs="*", default=DEFAULT_CLUSTERS,
                    help=f"集群列表，默认 {DEFAULT_CLUSTERS}")
    ap.add_argument("-b", "--bucket", default=BUCKET, help=f"桶名，默认 {BUCKET}")
    args = ap.parse_args()

    clusters = args.clusters

    print(f"采集各集群 MinIO 桶 `{args.bucket}` 状态...", file=sys.stderr)

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(len(clusters), 8)) as ex:
        futs = {ex.submit(fetch_cluster, c): c for c in clusters}
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                results[c] = fut.result()
            except Exception as e:
                print(f"[{c}] 采集失败: {e}", file=sys.stderr)
                results[c] = {"cluster": c, "objects": None,
                              "bytes": None, "write_rate": None, "read_rate": None}

    print()
    print(f"# MinIO `{args.bucket}` 集群状态")
    print(f"*{time.strftime('%Y-%m-%d %H:%M:%S')}*\n")

    header = "| 集群 | 对象数 | 容量 | 写入速率(6h) | 读取速率(6h) |"
    sep = "|------|--------|------|-------------|-------------|"
    print(header)
    print(sep)

    for c in clusters:
        info = results.get(c, {})
        objs = info.get("objects")
        byt = info.get("bytes")
        wr = info.get("write_rate")
        rr = info.get("read_rate")

        if objs is None:
            print(f"| **{c.upper()}** | ? | - | - | - |")
            continue

        print(f"| **{c.upper()}** | {_fmt_objs(objs)} | "
              f"{_fmt_bytes(byt)} | {_fmt_bps(wr)} | {_fmt_bps(rr)} |")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
