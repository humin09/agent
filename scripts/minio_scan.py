#!/usr/bin/env python3
"""各集群 MinIO gitlab-lfs-prod 同步进度检查

数据源：
  - 优先 VictoriaMetrics 指标 (所有有 VM 的集群)
  - 兜底 mc 命令 (xa 源站无 VM)

目标：以每个集群的 origin 为基准，对比 local 的 object count / 字节数 / batch replicate 进度。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests

requests.packages.urllib3.disable_warnings()

BUCKET = "gitlab-lfs-prod"

CLUSTER_ORIGINS = {
    "ks": {"origin": "xa", "endpoint": "http://221.11.21.199:9000"},
    "dz": {"origin": "ly", "endpoint": "http://oss.zzai.scnet.cn:9000"},
    "qd": {"origin": "ly", "endpoint": "http://oss.zzai.scnet.cn:9000"},
}

VM_ENDPOINTS = {
    "ks": "https://vm.ksai.scnet.cn:58043/select/0/prometheus",
    "dz": "https://vm.dzai.scnet.cn:58043/select/0/prometheus",
    "qd": "https://vm.qdai.scnet.cn:58043/select/0/prometheus",
    "ly": "https://vm.lyai.scnet.cn:58043/select/0/prometheus",
}

MC_ONLY_CLUSTERS = ["xa"]
# 默认包含源站 xa + ly，以及所有已接入 VM 的目的集群
DEFAULT_CLUSTERS = ["xa", "ly"] + [c for c in CLUSTER_ORIGINS]


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
        return "0.0 MB/s (0.00 TiB/h)"
    mb_s = bps / (1024 ** 2)
    tb_h = bps * 3600 / (1024 ** 4)
    if tb_h < 0.01:
        return f"{mb_s:.2f} MB/s"
    return f"{mb_s:.2f} MB/s ({tb_h:.2f} TiB/h)"


def _fmt_objs(n: Optional[int]) -> str:
    return f"{n:,}" if n is not None and n >= 0 else "-"


# ── mc 方式（xa 源站）─────────────────────────────────
_SOURCE_ALIASES: dict[str, str] = {}


def _ensure_mc_alias(alias: str, endpoint: str) -> str:
    """确保 mc 已配置 alias；若未配置则临时设置，并返回可用的 alias 名。"""
    if alias in _SOURCE_ALIASES:
        return _SOURCE_ALIASES[alias]
    # check existing
    try:
        p = subprocess.run(["mc", "alias", "list", alias],
                           capture_output=True, text=True, timeout=10)
        if p.returncode == 0 and "URL" in p.stdout and endpoint[:20] in p.stdout:
            _SOURCE_ALIASES[alias] = alias
            return alias
    except Exception:
        pass
    # set temp
    tmp = f"scan_{alias}"
    try:
        subprocess.run(
            ["mc", "alias", "set", tmp, endpoint, "admin", "SugonMinio2024_pro"],
            capture_output=True, text=True, timeout=30,
        )
        _SOURCE_ALIASES[alias] = tmp
        return tmp
    except Exception as e:
        print(f"[{alias}] mc alias set 失败: {e}", file=sys.stderr)
        return alias


def mc_bucket_stat(alias: str, bucket: str, endpoint: Optional[str] = None,
                    timeout: int = 180) -> tuple[Optional[int], Optional[int]]:
    """返回 (objects, bytes)；失败返回 (None, None)。"""
    real_alias = _ensure_mc_alias(alias, endpoint) if endpoint else alias
    try:
        p = subprocess.run(
            ["mc", "stat", f"{real_alias}/{bucket}"],
            capture_output=True, text=True, timeout=timeout,
        )
        if p.returncode != 0:
            print(f"[{alias}/{bucket}] mc stat 失败: {p.stderr.strip()}", file=sys.stderr)
            return None, None
        obj_m = re.search(r"Objects count\s*:\s*([\d,]+)", p.stdout)
        objs = int(obj_m.group(1).replace(",", "")) if obj_m else None
        sz_m = re.search(r"Total size\s*:\s*([\d.]+)\s*([A-Za-z]*)", p.stdout)
        byt = None
        if sz_m:
            val = float(sz_m.group(1))
            unit = sz_m.group(2).upper()
            units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3,
                     "TB": 1024**4, "TIB": 1024**4, "GIB": 1024**3, "MIB": 1024**2}
            byt = int(val * units.get(unit, 1))
        return objs, byt
    except Exception as e:
        print(f"[{alias}/{bucket}] mc stat 异常: {e}", file=sys.stderr)
        return None, None


# ── VM 方式 ─────────────────────────────────────────────
def vm_query(cluster: str, query: str) -> list[dict]:
    """返回 VM query 的 result 列表；失败返回空列表。"""
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
        print(f"[{cluster}] VM query 失败 ({query[:60]}...): {e}", file=sys.stderr)
        return []


def vm_bucket_usage(cluster: str, bucket: str) -> tuple[Optional[int], Optional[int]]:
    """返回 (objects, bytes)。"""
    objs_results = vm_query(
        cluster, f'minio_bucket_usage_object_total{{bucket="{bucket}"}}'
    )
    bytes_results = vm_query(
        cluster, f'minio_bucket_usage_total_bytes{{bucket="{bucket}"}}'
    )
    objs = None
    byt = None
    for r in objs_results:
        try:
            objs = max(objs or 0, int(float(r["value"][1])))
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    for r in bytes_results:
        try:
            byt = max(byt or 0, int(float(r["value"][1])))
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    return objs, byt


def vm_bucket_bytes_rate(cluster: str, bucket: str, window: str = "6h") -> Optional[float]:
    """返回 window 内平均写入速率 (bytes/sec)。默认 6h 以捕捉批量复制任务的稳定速率。"""
    results = vm_query(
        cluster,
        f'increase(minio_bucket_usage_total_bytes{{bucket="{bucket}"}}[{window}])',
    )
    window_secs = {"15m": 900, "1h": 3600, "3h": 10800, "6h": 21600, "1d": 86400}
    ws = window_secs.get(window, 3600)
    best: Optional[float] = None
    for r in results:
        try:
            v = float(r["value"][1])
            bps = v / ws if v > 0 else 0.0
            best = bps if best is None else max(best, bps)
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    return best


def vm_batch_replicate_object_rate(cluster: str, bucket: str, window: str = "6h") -> Optional[float]:
    """返回 window 内所有 batch replicate 任务的总 object 速率 (objects/sec)。"""
    results = vm_query(
        cluster,
        f'rate(minio_bucket_batch_replicate_objects{{bucket="{bucket}"}}[{window}])',
    )
    total_rate = 0.0
    for r in results:
        # 只统计 pod 级别的指标，避免重复计算 (job=minio vs job=minio-ks 会重复)
        if r.get("metric", {}).get("job", "").startswith("minio-"):
            continue
        try:
            v = float(r["value"][1])
            total_rate += max(0, v)
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    return total_rate if total_rate > 0 else None


def vm_batch_replicate_status(cluster: str, bucket: str) -> list[dict]:
    """返回各 jobId 的 (replicated, failed) 计数。"""
    repl = vm_query(
        cluster, f'minio_bucket_batch_replicate_objects{{bucket="{bucket}"}}'
    )
    fail = vm_query(
        cluster, f'minio_bucket_batch_replicate_objects_failed{{bucket="{bucket}"}}'
    )
    by_job: dict[str, dict] = {}
    for r in repl:
        job = r.get("metric", {}).get("jobId", "unknown")
        try:
            by_job.setdefault(job, {"replicated": 0, "failed": 0})
            by_job[job]["replicated"] = max(0, int(float(r["value"][1])))
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    for r in fail:
        job = r.get("metric", {}).get("jobId", "unknown")
        try:
            by_job.setdefault(job, {"replicated": 0, "failed": 0})
            by_job[job]["failed"] = max(0, int(float(r["value"][1])))
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    return [{"jobId": j, **v} for j, v in by_job.items()]


# ── 采集单个集群数据 ─────────────────────────────
def fetch_cluster(cluster: str) -> dict:
    """返回一个 dict 描述集群状态。"""
    info: dict = {"cluster": cluster}

    if cluster in VM_ENDPOINTS:
        # Try VM first; on failure, fall back to mc for source clusters only
        objs, byt = vm_bucket_usage(cluster, BUCKET)
        if objs is not None:
            bps = vm_bucket_bytes_rate(cluster, BUCKET, "6h")
            obj_rate = vm_batch_replicate_object_rate(cluster, BUCKET, "6h")
            batch = vm_batch_replicate_status(cluster, BUCKET)
            info.update(objects=objs, bytes=byt, bps=bps, obj_rate=obj_rate, batch=batch)
            return info
        # VM 不可达（如 ly），尝试 mc 兜底
        if cluster == "ly":
            print(f"[{cluster}] VM 不可达，回退到 mc 查询 oss.zzai.scnet.cn", file=sys.stderr)
            objs, byt = mc_bucket_stat("ly", BUCKET,
                                       endpoint="http://oss.zzai.scnet.cn:9000")
            info.update(objects=objs, bytes=byt, bps=None, obj_rate=None, batch=[])
            return info

    if cluster in MC_ONLY_CLUSTERS:
        # xa: 直接用 URL 作为 endpoint 设置临时 alias
        objs, byt = mc_bucket_stat(
            cluster, BUCKET, endpoint="http://221.11.21.199:9000"
        )
        info.update(objects=objs, bytes=byt, bps=None, obj_rate=None, batch=[])
        return info

    info.update(objects=None, bytes=None, bps=None, obj_rate=None, batch=[])
    return info


# ── 主流程 ────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "-c", "--clusters", nargs="*", default=DEFAULT_CLUSTERS,
        help=f"集群列表，默认 {DEFAULT_CLUSTERS}",
    )
    ap.add_argument("-b", "--bucket", default=BUCKET, help=f"桶名，默认 {BUCKET}")
    args = ap.parse_args()

    bucket = args.bucket
    clusters = args.clusters

    print(f"⏳ 采集各集群 MinIO 桶 `{bucket}` 状态...", file=sys.stderr)

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(len(clusters), 8)) as ex:
        futs = {ex.submit(fetch_cluster, c): c for c in clusters}
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                results[c] = fut.result()
            except Exception as e:
                print(f"[{c}] 采集失败: {e}", file=sys.stderr)
                results[c] = {"cluster": c, "objects": None, "bytes": None,
                              "bps": None, "batch": []}

    # xa 作为 xa 源集群本身；对于 dz/qd，源是 ly
    xa = results.get("xa", {})
    ly = results.get("ly", {})

    xa_objs = xa.get("objects")
    xa_byt = xa.get("bytes")
    ly_objs = ly.get("objects")
    ly_byt = ly.get("bytes")

    print()
    print(f"# MinIO `{bucket}` 同步进度检查")
    print(f"*{time.strftime('%Y-%m-%d %H:%M:%S')}*\n")
    print(f"**源站**：")
    print(f"- xa（西安 221.11.21.199:9000）：{_fmt_objs(xa_objs)} objects / {_fmt_bytes(xa_byt)}")
    print(f"- ly（oss.zzai.scnet.cn:9000 = 洛阳）：{_fmt_objs(ly_objs)} objects / {_fmt_bytes(ly_byt)}")
    print()

    header = "| 集群 | 源 | 对象数 | 进度 | 差距 | 容量 | 对象速率(6h) | 字节速率(6h) | ETA | batch job |"
    sep    = "|------|---|--------|------|------|------|-------------|-------------|-----|-----------|"
    print(header)
    print(sep)

    for c in clusters:
        src = CLUSTER_ORIGINS.get(c)
        if c == "xa":
            src_name = "(源)"
            src_objs = xa_objs
            src_byt = xa_byt
        elif c == "ly":
            # ly 不作为任何目的集群的 destination，单独显示
            src_name = "(源)"
            src_objs = ly_objs
            src_byt = ly_byt
        elif src:
            src_name = src["origin"]
            if src_name == "xa":
                src_objs = xa_objs
                src_byt = xa_byt
            elif src_name == "ly":
                src_objs = ly_objs
                src_byt = ly_byt
            else:
                src_objs = None
                src_byt = None
        else:
            src_name = "-"
            src_objs = None
            src_byt = None

        info = results.get(c, {})
        objs = info.get("objects")
        byt = info.get("bytes")
        bps = info.get("bps")
        obj_rate = info.get("obj_rate")
        batch = info.get("batch", [])

        if objs is None:
            print(f"| **{c.upper()}** | {src_name} | ❓ | - | - | - | - | - | - | - |")
            continue

        if src_objs is not None and src_objs > 0:
            diff = src_objs - objs
            pct = objs / src_objs * 100
            gap = f"-{diff:,}" if diff > 0 else "✅"
        else:
            pct = 0.0
            diff = None
            gap = "N/A"

        # 对象速率
        obj_rate_str = f"{obj_rate:.1f} obj/s" if obj_rate and obj_rate > 0 else "-"

        # 字节速率
        bps_str = _fmt_bps(bps)

        # ETA：基于剩余对象数和对象速率
        eta_str = "-"
        if obj_rate and obj_rate > 0 and diff is not None and diff > 0:
            eta_sec = diff / obj_rate
            if eta_sec < 3600:
                eta_str = f"{eta_sec/60:.0f}m"
            elif eta_sec < 86400:
                eta_str = f"{eta_sec/3600:.1f}h"
            else:
                eta_str = f"{eta_sec/86400:.1f}d"

        batch_summary = "-"
        if batch:
            parts = []
            for b in batch:
                jid = b["jobId"].split(":-")[0] if ":-" in b["jobId"] else b["jobId"]
                short = jid[-8:] if len(jid) > 8 else jid
                rep = b.get("replicated", 0)
                fail = b.get("failed", 0)
                parts.append(f"{short} (OK {rep:,}, fail {fail:,})")
            batch_summary = "<br>".join(parts)

        print(f"| **{c.upper()}** | {src_name} | {_fmt_objs(objs)} | {pct:.2f}% | {gap} | "
              f"{_fmt_bytes(byt)} | {obj_rate_str} | {bps_str} | {eta_str} | {batch_summary} |")

    print()
    return 0


SOURCE_XA = "xa"

if __name__ == "__main__":
    raise SystemExit(main())
