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
    "ly": {"origin": "xa", "endpoint": "http://221.11.21.199:9000"},
    "ks": {"origin": "ly", "endpoint": "http://oss.zzai.scnet.cn:9000"},
    "dz": {"origin": "ly", "endpoint": "http://oss.zzai.scnet.cn:9000"},
    "qd": {"origin": "ly", "endpoint": "http://oss.zzai.scnet.cn:9000"},
}

VM_ENDPOINTS = {
    "ks": "https://vm.ksai.scnet.cn:58043/select/0/prometheus",
    "dz": "https://vm.dzai.scnet.cn:58043/select/0/prometheus",
    "qd": "https://vm.qdai.scnet.cn:58043/select/0/prometheus",
    # ly 和 zz 是同一个集群的共享基础设施（vm, vl, minio, ex-lb），共用同一个 VM endpoint
    "ly": "https://vm.zzai.scnet.cn:58043/select/0/prometheus",
    "zz": "https://vm.zzai.scnet.cn:58043/select/0/prometheus",
}

MC_ONLY_CLUSTERS = ["xa"]
DEFAULT_CLUSTERS = list(dict.fromkeys(["xa", "ly"] + list(CLUSTER_ORIGINS.keys())))


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


# ── 直接抓取 minio 指标（ly 等公网可达但无 VM 的集群）─────────────

LY_METRICS_URL = "http://oss.zzai.scnet.cn:9000/minio/v2/metrics/cluster"

# 状态缓存：用于 ly 这种无 VM 的集群计算 rate
_STATE_FILE = "/tmp/minio_scan_state.json"


def _load_state() -> dict:
    try:
        with open(_STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return {}


def _save_state(state: dict) -> None:
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def scrape_minio_metrics(url: str, bucket: str) -> tuple[Optional[int], Optional[int]]:
    """直接从 minio /metrics endpoint 抓取指标，返回 (objects, bytes)。"""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        lines = resp.text.splitlines()

        objs = None
        byt = None

        for line in lines:
            if line.startswith("#"):
                continue
            # minio_bucket_usage_object_total
            m = re.match(rf'minio_bucket_usage_object_total{{.*bucket="{bucket}".*}} (\d+)', line)
            if m:
                objs = max(objs or 0, int(m.group(1)))
                continue
            # minio_bucket_usage_total_bytes
            m = re.match(rf'minio_bucket_usage_total_bytes{{.*bucket="{bucket}".*}} (\d+)', line)
            if m:
                byt = max(byt or 0, int(m.group(1)))
                continue

        return objs, byt
    except Exception as e:
        print(f"[metrics {url}] 抓取失败: {e}", file=sys.stderr)
        return None, None


# ── 读取 mirror job 进度文件 ─────────────────────
PROGRESS_FILE = "tmp/minio-mirror-progress/gitlab-lfs-prod.json"
TOTAL_PREFIXES = 256

def mc_mirror_progress(cluster: str) -> tuple[int, list[str]]:
    """读取 mirror job 进度文件，返回 (synced_count, synced_prefixes)。"""
    endpoint = "http://oss.zzai.scnet.cn:9000"
    real_alias = _ensure_mc_alias("ly-mirror", endpoint)
    try:
        p = subprocess.run(
            ["mc", "cat", f"{real_alias}/{PROGRESS_FILE}"],
            capture_output=True, text=True, timeout=30,
        )
        if p.returncode != 0:
            return 0, []
        data = json.loads(p.stdout)
        prefixes = data if isinstance(data, list) else []
        return len(prefixes), prefixes
    except Exception:
        return 0, []



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


def vm_bucket_download_rate(cluster: str, bucket: str, window: str = "6h") -> Optional[float]:
    """返回 window 内平均下载速率 (bytes/sec)。使用 bucket_traffic_sent_bytes rate。"""
    results = vm_query(
        cluster,
        f'rate(minio_bucket_traffic_sent_bytes{{bucket="{bucket}"}}[{window}])',
    )
    total_rate = 0.0
    for r in results:
        try:
            v = float(r["value"][1])
            total_rate += max(0, v)
        except (KeyError, ValueError, IndexError, TypeError):
            pass
    return total_rate if total_rate > 0 else None


# (deleted: vm_batch_replicate_object_rate and vm_batch_replicate_status)


# ── 采集单个集群数据 ─────────────────────────────
def fetch_cluster(cluster: str) -> dict:
    """返回一个 dict 描述集群状态。"""
    info: dict = {"cluster": cluster}

    if cluster in VM_ENDPOINTS:
        # Try VM first; on failure, fall back to mc for source clusters only
        objs, byt = vm_bucket_usage(cluster, BUCKET)
        if objs is not None:
            bps = vm_bucket_bytes_rate(cluster, BUCKET, "6h")
            # 写入状态缓存 (用于无 VM 集群计算 delta rate)
            dl_rate = vm_bucket_download_rate(cluster, BUCKET, "6h")

            # ly 集群读取 mirror job 进度
            mirror_progress = None
            if cluster == "ly":
                synced, prefixes = mc_mirror_progress(cluster)
                mirror_progress = {"synced": synced, "total": TOTAL_PREFIXES, "prefixes": prefixes}

            state = _load_state()
            state[cluster] = {"objects": objs, "bytes": byt, "timestamp": time.time()}
            _save_state(state)
            info.update(objects=objs, bytes=byt, bps=bps, dl_rate=dl_rate, mirror_progress=mirror_progress)
            return info

    if cluster in MC_ONLY_CLUSTERS:
        # xa: 直接用 URL 作为 endpoint 设置临时 alias
        objs, byt = mc_bucket_stat(
            cluster, BUCKET, endpoint="http://221.11.21.199:9000"
        )
        info.update(objects=objs, bytes=byt, bps=None, dl_rate=None, mirror_progress=None)
        return info

    info.update(objects=None, bytes=None, bps=None, dl_rate=None, mirror_progress=None)
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

    header = "| 集群 | 源 | 对象数 | 进度 | 差距 | 容量 | 下载速率(6h) | 同步速率(6h) | ETA | mirror 进度 |"
    sep    = "|------|---|--------|------|------|------|-------------|-------------|-----|-------------|"
    print(header)
    print(sep)

    for c in clusters:
        src = CLUSTER_ORIGINS.get(c)
        # ly = xa 的目的站 + dz/qd 的源站，需要特殊处理
        if c == "xa":
            src_name = "(源)"
            src_objs = None
            src_byt = None
        elif c == "ly":
            src_name = "xa"
            src_objs = xa_objs
            src_byt = xa_byt
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
        dl_rate = info.get("dl_rate")
        mirror_progress = info.get("mirror_progress")

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

        # 下载速率
        dl_rate_str = _fmt_bps(dl_rate)

        # 同步速率（基于下载速率估算字节写入速率）
        sync_rate_str = _fmt_bps(bps) if bps and bps > 0 else "-"

        # ETA：基于剩余字节数和写入速率
        eta_str = "-"
        if bps and bps > 0 and src_byt is not None and src_byt > 0 and byt is not None:
            remaining_bytes = src_byt - byt
            if remaining_bytes > 0:
                eta_sec = remaining_bytes / bps
                if eta_sec < 3600:
                    eta_str = f"{eta_sec/60:.0f}m"
                elif eta_sec < 86400:
                    eta_str = f"{eta_sec/3600:.1f}h"
                else:
                    eta_str = f"{eta_sec/86400:.1f}d"

        # mirror job 进度
        mirror_summary = "-"
        if mirror_progress:
            synced = mirror_progress["synced"]
            total = mirror_progress["total"]
            pct_mirror = f"{synced}/{total}"
            if synced == total:
                mirror_summary = f"{pct_mirror} ✅"
            else:
                mirror_summary = f"{pct_mirror} ⏳"

        print(f"| **{c.upper()}** | {src_name} | {_fmt_objs(objs)} | {pct:.2f}% | {gap} | "
              f"{_fmt_bytes(byt)} | {dl_rate_str} | {sync_rate_str} | {eta_str} | {mirror_summary} |")

    print()
    return 0


SOURCE_XA = "xa"

if __name__ == "__main__":
    raise SystemExit(main())
