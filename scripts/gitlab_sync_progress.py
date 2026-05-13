#!/usr/bin/env python3
"""
检查各集群 mc-client 的 gitlab-lfs 同步进度。

数据来源：
  1. 每个 Pod 的 /tmp/gitlab-sync-state.json —— 精确的 per-prefix 最终态
  2. ps 输出 —— 当前正在跑的 prefix
  3. /proc/net/dev 双采样 —— ex-lb 节点（hostNetwork）的实时网络速率
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

NS = "ske"
APP_LABEL = "app=mc-client"
STATE_PATH = "/tmp/gitlab-sync-state.json"
DEFAULT_CLUSTERS = ["ks", "qd", "dz", "zz"]
DEFAULT_WINDOW_HOURS = 3
RATE_WINDOW_MIN = 15


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


def fmt_summary(ctx: str, window_hours: int, rate_min: int) -> str:
    pods = list_pods(ctx)
    if not pods:
        return f"[{ctx}] no mc-client pods\n"

    window_seconds = window_hours * 3600
    rate_seconds = rate_min * 60

    lines = [f"\n=== [{ctx}] gitlab-lfs sync (window {window_hours}h, rate window {rate_min}min) ==="]

    total_recent_ok = total_recent_fail = 0
    total_done_ok = total_done_fail = 0
    total_rate = 0.0
    per_pod = []
    aggregated_state: dict = {}

    for pod, node_ip in pods:
        state = read_state(ctx, pod)
        running = read_running_prefix(ctx, pod)
        win = aggregate_window(state, window_seconds)
        rate = compute_rate(state, rate_seconds)
        rx, tx = pod_net_rate(ctx, pod)

        per_pod.append({
            "pod": pod, "node": node_ip, "shard_entries": len(state),
            "win": win, "running": running, "rate": rate, "rx": rx, "tx": tx,
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

    # cluster-wide totals from merged state
    cluster_win = aggregate_window(aggregated_state, window_seconds)

    # Total prefixes: 65536 (00/00 to ff/ff for level-2, or 256 for level-1)
    total_prefixes = 65536
    lines.append(
        f"  cluster total: prefixes_seen={len(aggregated_state)}/{total_prefixes}  "
        f"success={total_done_ok}  failed={total_done_fail}"
    )
    lines.append(
        f"  last {window_hours}h: success={cluster_win['success']}  "
        f"failed={cluster_win['failed']}  "
        f"(per-pod sum: ok={total_recent_ok} fail={total_recent_fail})"
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
    args = ap.parse_args()

    for ctx in args.contexts:
        try:
            sys.stdout.write(fmt_summary(ctx, args.window_hours, args.rate_min))
            sys.stdout.flush()
        except subprocess.TimeoutExpired:
            print(f"[{ctx}] timeout", file=sys.stderr)
        except Exception as e:
            print(f"[{ctx}] error: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
