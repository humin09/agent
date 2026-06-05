#!/usr/bin/env python3
"""
检查各集群 mc-client 的 gitlab-lfs 同步进度 + MinIO 核心指标综合报告。

数据来源：
  1. 每个 Pod 的 /tmp/gitlab-sync-state.json —— 精确的 per-prefix 最终态
  2. ps 输出 —— 当前正在跑的 prefix
  3. /proc/net/dev 双采样 —— ex-lb 节点（hostNetwork）的实时网络速率
  4. VictoriaMetrics 查询 —— MinIO 集群和桶级指标
"""
from __future__ import annotations

import argparse
import json

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import urllib.parse
from typing import Optional, Dict, Any

requests.packages.urllib3.disable_warnings()

NS = "ske"
APP_LABEL = "app=mc-client"
STATE_PATH = "/tmp/gitlab-sync-state.json"
DEFAULT_CLUSTERS = ["ks", "dz", "zz", "qd"]
DEFAULT_WINDOW_HOURS = 3
RATE_WINDOW_MIN = 15
STATE_READ_RETRIES = 6
STATE_READ_RETRY_DELAY = 1.0
STATE_STABLE_READS = 2

CLUSTER_VM_URLS = {
    "ks": "https://vm.ksai.scnet.cn:58043/select/0/prometheus",
    "dz": "https://vm.dzai.scnet.cn:58043/select/0/prometheus",
    "zz": "https://vm.zzai.scnet.cn:58043/select/0/prometheus",
    "qd": "https://vm.qdai.scnet.cn:58043/select/0/prometheus",
}

TOTAL_PREFIXES = 65536
IGNORE_BUCKETS = {"loki", "prom", "tmp", "k8s"}


def should_ignore_bucket(bucket: str) -> bool:
    """过滤系统桶：精确匹配 loki/prom/tmp/k8s，及所有 k8s* 前缀桶。"""
    return bucket in IGNORE_BUCKETS or bucket.startswith("k8s")


class MetricsClient:
    def __init__(self, cluster: str):
        self.cluster = cluster
        self.base_url = CLUSTER_VM_URLS.get(cluster, "").rstrip("/")
        self.session = requests.Session()
        self.session.verify = False

    def query(self, promql: str) -> Optional[Dict[str, Any]]:
        """执行 PromQL 即时查询"""
        if not self.base_url:
            return None
        try:
            params = {
                "query": promql,
                "time": time.time(),
                "dedup": "true",
                "partial_response": "true",
            }
            response = self.session.get(
                f"{self.base_url}/api/v1/query",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[{self.cluster}] 指标查询失败: {e}", file=sys.stderr)
            return None

    def parse_vector_result(self, result: Optional[Dict]) -> Dict[str, float]:
        """解析向量查询结果，返回 {label_str: value} 的映射"""
        if not result or result.get("status") != "success":
            return {}
        values = result.get("data", {}).get("result", [])
        ret = {}
        for item in values:
            metric = item.get("metric", {})
            val = item.get("value", [0, "0"])[1]
            label_str = ", ".join(f"{k}={v}" for k, v in metric.items())
            try:
                ret[label_str] = float(val)
            except ValueError:
                pass
        return ret


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def list_pods(ctx: str) -> list[tuple[str, str]]:
    """Return [(pod_name, node_ip), ...]."""
    rc, out, _ = run([
        "kubectl", "--context", ctx, "-n", NS,
        "get", "pod", "-l", APP_LABEL,
        "-o", "jsonpath={range .items[*]}{.metadata.name},{.status.hostIP}\n{end}",
    ])
    if rc != 0:
        return []
    pods = []
    for line in out.strip().splitlines():
        if "," in line:
            name, ip = line.split(",", 1)
            if name and ip:
                pods.append((name.strip(), ip.strip()))
    return sorted(pods)


def read_state(ctx: str, pod: str) -> dict:
    rc, out, _ = run([
        "kubectl", "--context", ctx, "-n", NS,
        "exec", pod, "--", "cat", STATE_PATH,
    ])
    if rc != 0 or not out.strip():
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def read_state_raw(ctx: str, pod: str) -> str:
    """读取状态文件原文，失败时返回空字符串。"""
    rc, out, _ = run([
        "kubectl", "--context", ctx, "-n", NS,
        "exec", pod, "--", "cat", STATE_PATH,
    ])
    if rc != 0:
        return ""
    return out


def read_state_stable(
    ctx: str,
    pod: str,
    retries: int = STATE_READ_RETRIES,
    delay: float = STATE_READ_RETRY_DELAY,
    stable_reads: int = STATE_STABLE_READS,
) -> tuple[dict, bool]:
    """读取状态文件，能解析为合法 JSON 即视为稳定。"""
    for attempt in range(1, retries + 1):
        raw = read_state_raw(ctx, pod)
        if not raw.strip():
            if attempt < retries:
                time.sleep(delay)
            continue

        try:
            state = json.loads(raw)
        except json.JSONDecodeError:
            if attempt < retries:
                time.sleep(delay)
            continue

        return state, True
    return {}, False


def collect_pod_snapshot(ctx: str, pod: str, node_ip: str) -> dict[str, Any]:
    """并发采集单个 mc-client pod 的快照。"""
    state, stable = read_state_stable(ctx, pod)
    return {
        "pod": pod,
        "node": node_ip,
        "state": state,
        "stable": stable,
        "running": read_running_prefix(ctx, pod),
        "rx_tx": pod_net_rate(ctx, pod),
    }


def read_running_prefix(ctx: str, pod: str) -> str | None:
    rc, out, _ = run([
        "kubectl", "--context", ctx, "-n", NS,
        "exec", pod, "--", "sh", "-c",
        "ps -ef | grep '[m]c mirror' | head -1",
    ])
    if rc != 0:
        return None
    for tok in out.split():
        if tok.startswith("origin/gitlab-lfs-prod/"):
            parts = tok.split("/")
            if len(parts) >= 3:
                return parts[-2] or parts[-1]
    return None


def aggregate_window(state: dict, window_seconds: int) -> dict:
    """统计 state 中近 window 内的 success / failure / cooldown_skip."""
    now = time.time()
    cutoff = now - window_seconds
    summary = {"success": 0, "failed": 0, "older_success": 0, "older_failed": 0}
    for _, v in state.items():
        r = v.get("last_result")
        if r == "success":
            ts = v.get("last_success_ts", 0)
            if ts >= cutoff:
                summary["success"] += 1
            else:
                summary["older_success"] += 1
        elif r == "failed":
            ts = v.get("last_failure_ts", 0)
            if ts >= cutoff:
                summary["failed"] += 1
            else:
                summary["older_failed"] += 1
    return summary


def compute_rate(state: dict, rate_window_seconds: int) -> float:
    """近 rate_window 的成功 prefix 数 / 分钟."""
    now = time.time()
    cutoff = now - rate_window_seconds
    n = sum(
        1 for v in state.values()
        if v.get("last_result") == "success" and v.get("last_success_ts", 0) >= cutoff
    )
    minutes = rate_window_seconds / 60
    return n / minutes if minutes else 0


SKIP_IFACES = {"lo"}
SKIP_PREFIX = ("cali", "tunl", "veth", "docker", "flannel", "kube-ipvs", "nodelocaldns", "ib")


def _read_net_counters(ctx: str, pod: str) -> tuple[int, int] | None:
    """Sum rx/tx bytes from /proc/net/dev inside the pod (hostNetwork → host counters).

    NOTE: hostNetwork=true means we're sampling the **host's** total traffic, not
    just this pod's. On dedicated ex-lb nodes running only mc-client + nginx, this
    approximates mc-client throughput well enough for monitoring.
    """
    rc, out, _ = run([
        "kubectl", "--context", ctx, "-n", NS,
        "exec", pod, "--", "cat", "/proc/net/dev",
    ])
    if rc != 0:
        return None
    rx = tx = 0
    for line in out.splitlines():
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        iface = iface.strip()
        if iface in SKIP_IFACES or any(iface.startswith(p) for p in SKIP_PREFIX):
            continue
        fields = rest.split()
        if len(fields) >= 9:
            try:
                rx += int(fields[0])
                tx += int(fields[8])
            except ValueError:
                continue
    return rx, tx


def pod_net_rate(ctx: str, pod: str, interval: float = 2.0) -> tuple[float, float]:
    """Two snapshots `interval` seconds apart → MiB/s rx/tx."""
    a = _read_net_counters(ctx, pod)
    if a is None:
        return (0.0, 0.0)
    time.sleep(interval)
    b = _read_net_counters(ctx, pod)
    if b is None:
        return (0.0, 0.0)
    rx = (b[0] - a[0]) / interval / (1024 ** 2)
    tx = (b[1] - a[1]) / interval / (1024 ** 2)
    return max(rx, 0.0), max(tx, 0.0)


def fetch_minio_metrics(ctx: str) -> Dict[str, Any]:
    """收集 MinIO 集群级和桶级指标"""
    client = MetricsClient(ctx)
    if not client.base_url:
        return {}

    metrics = {}

    # 集群级指标
    cluster_queries = {
        "health": "minio_cluster_health_status",
        "nodes_online": "minio_cluster_nodes_online_total",
        "capacity_total": "minio_cluster_capacity_usable_total_bytes",
        "capacity_free": "minio_cluster_capacity_usable_free_bytes",
        "usage": "minio_cluster_usage_total_bytes",
        "requests_rate": "sum(rate(minio_s3_requests_total[5m]))",
        "errors_rate": "sum(rate(minio_s3_requests_errors_total[5m]))",
        "rx_rate": "sum(rate(minio_s3_traffic_received_bytes[5m]))",
        "tx_rate": "sum(rate(minio_s3_traffic_sent_bytes[5m]))",
    }

    for key, query in cluster_queries.items():
        result = client.query(query)
        if result and result.get("status") == "success":
            values = result.get("data", {}).get("result", [])
            if values:
                val = float(values[0].get("value", [0, "0"])[1])
                metrics[key] = val

    # 桶级指标（聚合，排除 loki 和 prom）
    bucket_queries = {
        "bucket_size": "sum(minio_bucket_usage_total_bytes) by (bucket)",
        "bucket_objects": "sum(minio_bucket_usage_object_total) by (bucket)",
        "bucket_rx": "sum(rate(minio_bucket_traffic_received_bytes[5m])) by (bucket)",
        "bucket_tx": "sum(rate(minio_bucket_traffic_sent_bytes[5m])) by (bucket)",
        "bucket_requests": "sum(rate(minio_bucket_requests_total[5m])) by (bucket)",
        "bucket_4xx": "sum(rate(minio_bucket_requests_4xx_errors_total[5m])) by (bucket)",
        "bucket_5xx": "sum(rate(minio_bucket_requests_5xx_errors_total[5m])) by (bucket)",
    }

    bucket_data = {}
    for key, query in bucket_queries.items():
        result = client.query(query)
        if result and result.get("status") == "success":
            values = result.get("data", {}).get("result", [])
            for item in values:
                bucket = item.get("metric", {}).get("bucket", "unknown")
                # 跳过忽略的桶
                if should_ignore_bucket(bucket):
                    continue
                val = float(item.get("value", [0, "0"])[1])
                if bucket not in bucket_data:
                    bucket_data[bucket] = {}
                bucket_data[bucket][key] = val

    metrics["buckets"] = bucket_data
    return metrics


def collect_sync_report(ctx: str, window_hours: int, rate_min: int) -> dict[str, Any]:
    """采集单个集群的同步状态，返回结构化报告数据。"""
    pods = list_pods(ctx)
    if not pods:
        raise RuntimeError(f"[{ctx}] 无 mc-client pods")

    window_seconds = window_hours * 3600
    rate_seconds = rate_min * 60

    total_recent_ok = total_recent_fail = 0
    total_done_ok = total_done_fail = 0
    total_rate = 0.0
    per_pod = []
    aggregated_state: dict = {}

    pod_results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(len(pods), 8)) as executor:
        future_map = {executor.submit(collect_pod_snapshot, ctx, pod, node_ip): pod for pod, node_ip in pods}
        for future in as_completed(future_map):
            pod = future_map[future]
            try:
                pod_results[pod] = future.result()
            except Exception as e:
                pod_results[pod] = {
                    "state": {},
                    "stable": False,
                    "running": None,
                    "rx_tx": (0.0, 0.0),
                    "error": e,
                    "pod": pod,
                    "node": next((n for p, n in pods if p == pod), ""),
                }

    unstable_pods = [pod for pod, result in pod_results.items() if not result.get("stable")]
    missing_pods = [pod for pod, result in pod_results.items() if not result.get("state")]
    if unstable_pods or missing_pods:
        details = []
        if unstable_pods:
            details.append(f"未稳定的 pod: {', '.join(unstable_pods)}")
        if missing_pods:
            details.append(f"空状态 pod: {', '.join(missing_pods)}")
        raise RuntimeError(f"[{ctx}] 未能读取到稳定状态，{'；'.join(details)}")

    for pod, node_ip in pods:
        result = pod_results.get(pod, {})
        state = result.get("state", {})
        running = result.get("running")
        rx, tx = result.get("rx_tx", (0.0, 0.0))

        win = aggregate_window(state, window_seconds)
        rate = compute_rate(state, rate_seconds)

        per_pod.append({
            "pod": pod,
            "node": node_ip,
            "shard_entries": len(state),
            "win": win,
            "running": running,
            "rate": rate,
            "rx": rx,
            "tx": tx,
        })
        total_recent_ok += win["success"]
        total_recent_fail += win["failed"]
        total_done_ok += win["success"] + win["older_success"]
        total_done_fail += win["failed"] + win["older_failed"]
        total_rate += rate
        # aggregate latest state per prefix (take the one with latest activity)
        for k, v in state.items():
            cur = aggregated_state.get(k)
            v_ts = max(v.get("last_success_ts", 0), v.get("last_failure_ts", 0))
            if not cur:
                aggregated_state[k] = v
            else:
                cur_ts = max(cur.get("last_success_ts", 0), cur.get("last_failure_ts", 0))
                if v_ts > cur_ts:
                    aggregated_state[k] = v

    if any(result.get("stable") is False for result in pod_results.values()):
        raise RuntimeError(f"[{ctx}] 状态文件未达到稳定读取条件，已拒绝汇总")

    cluster_win = aggregate_window(aggregated_state, window_seconds)
    prefixes_done = len(aggregated_state)
    active_pods = [p["pod"] for p in per_pod if p.get("running")]
    sync_complete = prefixes_done >= TOTAL_PREFIXES and not active_pods

    return {
        "ctx": ctx,
        "pods": per_pod,
        "aggregated_state": aggregated_state,
        "cluster_win": cluster_win,
        "total_recent_ok": total_recent_ok,
        "total_recent_fail": total_recent_fail,
        "total_done_ok": total_done_ok,
        "total_done_fail": total_done_fail,
        "total_rate": total_rate,
        "total_prefixes": TOTAL_PREFIXES,
        "prefixes_done": prefixes_done,
        "active_pods": active_pods,
        "sync_complete": sync_complete,
        "sync_status": "✅" if sync_complete else "⌛️",
        "sync_progress": "已完成" if sync_complete else f"进行中 ({prefixes_done}/{TOTAL_PREFIXES})",
        "window_hours": window_hours,
        "rate_min": rate_min,
    }


def format_sync_summary(report: dict[str, Any], markdown: bool = True) -> str:
    """根据结构化同步报告输出 Markdown 或纯文本。"""
    ctx = report["ctx"]
    window_hours = report["window_hours"]
    rate_min = report["rate_min"]
    per_pod = report["pods"]
    total_done_ok = report["total_done_ok"]
    total_done_fail = report["total_done_fail"]
    total_rate = report["total_rate"]
    cluster_win = report["cluster_win"]
    prefixes_done = report["prefixes_done"]
    total_prefixes = report["total_prefixes"]

    if markdown:
        lines = [f"#### {ctx.upper()} 集群\n"]
        lines.append(f"**同步状态**：{report['sync_status']} {report['sync_progress']}")
        lines.append(f"**历史统计**：成功 {total_done_ok} | 失败 {total_done_fail}")
        lines.append(f"**近 {window_hours}h**：成功 {cluster_win['success']} | 失败 {cluster_win['failed']}")
        lines.append(f"**同步速率**：{total_rate:.2f} prefix/min")
        lines.append(f"**已见前缀**：{prefixes_done}/{total_prefixes}\n")

        lines.append("| Pod | 节点 | 条目数 | 近期成功/失败 | 速率(/min) | RX/TX(MiB/s) | 当前处理 |")
        lines.append("|-----|------|--------|--------------|----------|--------------|---------|")

        for p in per_pod:
            lines.append(
                f"| {p['pod']} | {p['node']} | {p['shard_entries']} | "
                f"{p['win']['success']}/{p['win']['failed']} | {p['rate']:.2f} | "
                f"{p['rx']:6.1f}/{p['tx']:6.1f} | {p['running'] or '-'} |"
            )
        lines.append("")
        return "\n".join(lines)

    lines = [f"\n=== [{ctx}] gitlab-lfs sync (window {window_hours}h, rate window {rate_min}min) ==="]
    lines.append(
        f"  sync: {report['sync_progress']}  "
        f"history success={total_done_ok} failed={total_done_fail}"
    )
    lines.append(
        f"  last {window_hours}h: success={cluster_win['success']}  "
        f"failed={cluster_win['failed']}"
    )
    lines.append(
        f"  rate (last {rate_min}m): {total_rate:.2f} prefix/min"
    )
    for p in per_pod:
        lines.append(
            f"  - {p['pod']:13s} node={p['node']:15s} "
            f"entries={p['shard_entries']:3d}  "
            f"recent ok/fail={p['win']['success']}/{p['win']['failed']}  "
            f"rate={p['rate']:.2f}/min  "
            f"net rx/tx={p['rx']:6.1f}/{p['tx']:6.1f} MiB/s  "
            f"now={p['running'] or '-'}"
        )

    return "\n".join(lines) + "\n"


def format_bucket_section(ctx: str, buckets: dict[str, dict[str, float]]) -> list[str]:
    """输出单个集群的桶分析，排除系统桶。"""
    lines = [f"#### {ctx.upper()} 集群\n"]
    filtered_buckets = {
        bucket: data for bucket, data in buckets.items()
        if not should_ignore_bucket(bucket)
    }
    if not filtered_buckets:
        lines.append("*无可分析桶（已排除 loki/prom/tmp/k8s）*\n")
        return lines

    sorted_buckets = sorted(
        filtered_buckets.items(),
        key=lambda x: x[1].get("bucket_size", 0),
        reverse=True,
    )

    lines.append("| 桶名 | 大小(GB) | 对象数 | 上传(MB/s) | 下载(MB/s) | 请求/5m | 4xx错误 | 5xx错误 | 总错误率 |")
    lines.append("|------|----------|--------|-----------|-----------|---------|---------|---------|----------|")

    for bucket, data in sorted_buckets:
        size_gb = data.get("bucket_size", 0) / (1024**3)
        objs = int(data.get("bucket_objects", 0))
        rx_mb = data.get("bucket_rx", 0) / (1024**2)
        tx_mb = data.get("bucket_tx", 0) / (1024**2)
        req = data.get("bucket_requests", 0)
        err_4xx = data.get("bucket_4xx", 0)
        err_5xx = data.get("bucket_5xx", 0)
        err_total = err_4xx + err_5xx
        err_pct = (err_total / req * 100) if req > 0 else 0

        lines.append(
            f"| {bucket} | {size_gb:.2f} | {objs} | {rx_mb:.2f} | {tx_mb:.2f} | {req:.0f} | "
            f"{err_4xx:.0f} | {err_5xx:.0f} | {err_pct:.2f}% |"
        )

    lines.append("")
    return lines


def fmt_summary(ctx: str, window_hours: int, rate_min: int, markdown: bool = True) -> str:
    """生成 gitlab-lfs 同步进度报告（支持 markdown 表格格式）"""
    try:
        report = collect_sync_report(ctx, window_hours, rate_min)
    except Exception as exc:
        return f"[{ctx}] 同步进度采集失败：{exc}\n"
    return format_sync_summary(report, markdown=markdown)


def format_bytes(b: float) -> str:
    """格式化字节数为可读单位"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.2f}{unit}"
        b /= 1024
    return f"{b:.2f}PB"


def format_rate(val: float, unit: str = "/s") -> str:
    """格式化速率"""
    for prefix in ("", "K", "M", "G"):
        if val < 1000:
            return f"{val:.2f}{prefix}{unit}"
        val /= 1000
    return f"{val:.2f}T{unit}"


def parallel_map_contexts(contexts: list[str], worker, max_workers: int | None = None) -> dict[str, Any]:
    """并行处理各集群任务，返回 {ctx: result}。"""
    if not contexts:
        return {}

    if max_workers is None:
        max_workers = min(len(contexts), 4)

    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(worker, ctx): ctx for ctx in contexts}
        for future in as_completed(future_map):
            ctx = future_map[future]
            try:
                results[ctx] = future.result()
            except Exception as e:
                results[ctx] = e
    return results


def gen_comprehensive_report(contexts: list[str], window_hours: int, rate_min: int) -> str:
    """生成综合报告：gitlab-lfs 同步进度 + MinIO 指标"""
    lines = []
    lines.append("# MinIO 与 GitLab-LFS 同步综合监控报告")
    lines.append(f"*生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}*\n")

    # 第一部分：集群同步完成态
    lines.append("## 📊 一、集群同步完成态\n")
    sync_reports = parallel_map_contexts(contexts, lambda ctx: collect_sync_report(ctx, window_hours, rate_min))
    for ctx in contexts:
        result = sync_reports.get(ctx)
        if isinstance(result, Exception):
            lines.append(f"#### {ctx.upper()} 集群\n")
            lines.append(f"**同步状态**：⌛️ 采集失败 ({result})\n")
            continue
        lines.append(f"#### {ctx.upper()} 集群\n")
        lines.append(f"**同步状态**：{result['sync_status']} {result['sync_progress']}")
        lines.append(f"**历史统计**：成功 {result['total_done_ok']} | 失败 {result['total_done_fail']}")
        lines.append(f"**近 {window_hours}h**：成功 {result['cluster_win']['success']} | 失败 {result['cluster_win']['failed']}")
        lines.append(f"**同步速率**：{result['total_rate']:.2f} prefix/min")
        lines.append("")

    # 第二部分：MinIO 集群指标
    lines.append("## 🔧 二、MinIO 桶分析\n")

    metrics_results = parallel_map_contexts(contexts, fetch_minio_metrics)
    all_metrics = {}
    for ctx in contexts:
        result = metrics_results.get(ctx, {})
        if isinstance(result, Exception):
            print(f"[{ctx}] MinIO 指标查询失败: {result}", file=sys.stderr)
            all_metrics[ctx] = {}
        else:
            all_metrics[ctx] = result

    # 2.1 集群级指标对比表
    lines.append("### 2.1 集群级指标对比\n")
    lines.append("| 集群 | 健康 | 节点 | 容量(GB) | 使用(GB) | 使用率 | 请求/5m | 错误/5m | 错误率 | 上传(GB/s) | 下载(GB/s) |")
    lines.append("|------|------|------|----------|----------|--------|-----------|----------|--------|-------------|------------|")

    for ctx in contexts:
        m = all_metrics.get(ctx, {})
        if not m:
            lines.append(f"| {ctx} | ❌ | - | - | - | - | - | - | - | - | - |")
            continue

        health = "✓" if m.get("health") == 1 else "❌"
        nodes = int(m.get("nodes_online", 0))
        cap_total = m.get("capacity_total", 0) / (1024**3)
        cap_free = m.get("capacity_free", 0) / (1024**3)
        usage = cap_total - cap_free
        usage_rate = (usage / cap_total * 100) if cap_total > 0 else 0
        req_rate = m.get("requests_rate", 0)
        err_rate = m.get("errors_rate", 0)
        err_pct = (err_rate / req_rate * 100) if req_rate > 0 else 0
        rx = m.get("rx_rate", 0) / (1024**3)
        tx = m.get("tx_rate", 0) / (1024**3)

        lines.append(
            f"| {ctx} | {health} | {nodes} | {cap_total:.1f} | {usage:.1f} | {usage_rate:.1f}% | "
            f"{req_rate:.0f} | {err_rate:.0f} | {err_pct:.1f}% | {rx:.2f} | {tx:.2f} |"
        )

    # 2.2 各集群桶级详情
    lines.append("\n### 2.2 各集群桶级指标详情\n")

    for ctx in contexts:
        m = all_metrics.get(ctx, {})
        if not m or "buckets" not in m:
            continue

        lines.extend(format_bucket_section(ctx, m.get("buckets", {})))

    # 第三部分：关键告警和建议
    lines.append("\n## ⚠️ 三、关键告警与建议\n")

    alerts = []
    for ctx in contexts:
        m = all_metrics.get(ctx, {})
        if not m:
            continue

        # 容量告警
        cap_total = m.get("capacity_total", 0)
        cap_free = m.get("capacity_free", 0)
        if cap_total > 0:
            usage_rate = 1 - (cap_free / cap_total)
            if usage_rate > 0.8:
                alerts.append(f"🔴 **[{ctx}] 容量告急**：使用率 {usage_rate*100:.1f}%，需立即扩容")
            elif usage_rate > 0.7:
                alerts.append(f"🟡 **[{ctx}] 容量预警**：使用率 {usage_rate*100:.1f}%，建议规划扩容")

        # 错误率告警
        req_rate = m.get("requests_rate", 0)
        err_rate = m.get("errors_rate", 0)
        if req_rate > 0:
            err_pct = err_rate / req_rate * 100
            if err_pct > 10:
                alerts.append(f"🔴 **[{ctx}] 高错误率**：{err_pct:.1f}%，需排查应用或网络")
            elif err_pct > 5:
                alerts.append(f"🟡 **[{ctx}] 错误率升高**：{err_pct:.1f}%，需关注")

        # 集群健康告警
        if m.get("health") != 1:
            alerts.append(f"🔴 **[{ctx}] 集群不健康**：需立即排查")

    if alerts:
        for alert in alerts:
            lines.append(f"- {alert}")
    else:
        lines.append("✅ 暂无告警")

    lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "-c", "--contexts", nargs="*", default=DEFAULT_CLUSTERS,
        help=f"集群列表，默认 {' '.join(DEFAULT_CLUSTERS)}",
    )
    ap.add_argument(
        "--window-hours", type=int, default=DEFAULT_WINDOW_HOURS,
        help="统计窗口，单位小时（默认 3）",
    )
    ap.add_argument(
        "--rate-min", type=int, default=RATE_WINDOW_MIN,
        help="速率窗口，单位分钟（默认 15）",
    )
    ap.add_argument(
        "--minio-only", action="store_true",
        help="仅显示 MinIO 指标报告，跳过 gitlab-lfs 同步进度",
    )
    ap.add_argument(
        "--output", "-o", default="~/agent/reports/",
        help="输出目录（默认 ~/agent/reports/）",
    )
    args = ap.parse_args()

    # 确保输出目录存在
    import os
    output_dir = os.path.expanduser(args.output)
    os.makedirs(output_dir, exist_ok=True)

    if args.minio_only:
        # 只生成 MinIO 报告
        lines = []
        lines.append("# MinIO 集群监控报告")
        lines.append(f"*生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}*\n")

        metrics_results = parallel_map_contexts(args.contexts, fetch_minio_metrics)
        all_metrics = {}
        for ctx in args.contexts:
            result = metrics_results.get(ctx, {})
            if isinstance(result, Exception):
                print(f"[{ctx}] MinIO 指标查询失败: {result}", file=sys.stderr)
                all_metrics[ctx] = {}
            else:
                all_metrics[ctx] = result

        # 集群级指标对比
        lines.append("## 集群级指标对比\n")
        lines.append("| 集群 | 健康 | 节点 | 容量(GB) | 使用(GB) | 使用率 | 请求/5m | 错误/5m | 错误率 | 上传(GB/s) | 下载(GB/s) |")
        lines.append("|------|------|------|----------|----------|--------|-----------|----------|--------|-------------|------------|")

        for ctx in args.contexts:
            m = all_metrics.get(ctx, {})
            if not m:
                lines.append(f"| {ctx} | ❌ | - | - | - | - | - | - | - | - | - |")
                continue

            health = "✓" if m.get("health") == 1 else "❌"
            nodes = int(m.get("nodes_online", 0))
            cap_total = m.get("capacity_total", 0) / (1024**3)
            cap_free = m.get("capacity_free", 0) / (1024**3)
            usage = cap_total - cap_free
            usage_rate = (usage / cap_total * 100) if cap_total > 0 else 0
            req_rate = m.get("requests_rate", 0)
            err_rate = m.get("errors_rate", 0)
            err_pct = (err_rate / req_rate * 100) if req_rate > 0 else 0
            rx = m.get("rx_rate", 0) / (1024**3)
            tx = m.get("tx_rate", 0) / (1024**3)

            lines.append(
                f"| {ctx} | {health} | {nodes} | {cap_total:.1f} | {usage:.1f} | {usage_rate:.1f}% | "
                f"{req_rate:.0f} | {err_rate:.0f} | {err_pct:.1f}% | {rx:.2f} | {tx:.2f} |"
            )

        # 桶级详情
        lines.append("\n## 桶级指标详情\n")
        for ctx in args.contexts:
            m = all_metrics.get(ctx, {})
            if not m or "buckets" not in m:
                continue

            lines.extend(format_bucket_section(ctx, m.get("buckets", {})))

        report_content = "\n".join(lines)
        # 保存 MinIO 报告
        report_file = os.path.join(output_dir, "minio-report.md")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_content)
        sys.stdout.write(report_content)
        sys.stdout.flush()
        print(f"\n✅ 报告已保存到：{report_file}", file=sys.stderr)
    else:
        # 生成综合报告
        report = gen_comprehensive_report(args.contexts, args.window_hours, args.rate_min)
        # 保存综合报告
        report_file = os.path.join(output_dir, "minio-report.md")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        sys.stdout.write(report)
        sys.stdout.flush()
        print(f"\n✅ 报告已保存到：{report_file}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
