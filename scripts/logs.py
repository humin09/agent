#!/usr/bin/env python3
"""日志查询工具

优先使用 kubectl logs（活跃 Pod），降级到 Victoria Logs（历史日志）。
"""

import argparse
import json
import re
import subprocess
import sys
import urllib3
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


CLUSTER_VL_URLS = {
    "ks": "https://vl.ksai.scnet.cn:58043",
    "zz": "https://vl.zzai2.scnet.cn:58043",
    "dz": "https://vl.dzai.scnet.cn:58043",
    "qd": "https://vl.qdai.scnet.cn:58043",
    "sz": "https://vl.szai.scnet.cn:58043",
    "wq": "https://vl.sd5ai.scnet.cn:58043",
    "wh": "https://vl.whai.scnet.cn:58043",
}


def resolve_vl_url(context: str = None, explicit_url: str = None) -> str:
    """优先使用显式 URL，其次按 context 自动选择 VictoriaLogs 地址。"""
    if explicit_url:
        return explicit_url

    if context:
        cluster = context.lower()
        if cluster in CLUSTER_VL_URLS:
            return CLUSTER_VL_URLS[cluster]
        print(f"[WARN] context {context} 未配置专属 VictoriaLogs URL，使用 ks 默认地址", file=sys.stderr)

    return CLUSTER_VL_URLS["ks"]


def parse_time(time_str: str) -> str:
    """
    解析时间字符串，支持相对时间和绝对时间。
    相对时间: 1h, 2d, 30m (转换为 RFC3339)
    绝对时间: 2026-05-12T10:30:00Z (直接返回)
    """
    if time_str == "now":
        return datetime.utcnow().isoformat() + "Z"

    match = re.match(r"^(\d+)([hdms])$", time_str)
    if match:
        value = int(match.group(1))
        unit = match.group(2)

        delta_map = {
            "h": timedelta(hours=value),
            "d": timedelta(days=value),
            "m": timedelta(minutes=value),
            "s": timedelta(seconds=value),
        }
        delta = delta_map[unit]
        result = datetime.utcnow() - delta
        return result.isoformat() + "Z"

    return time_str


def query_logs(base_url: str, query: str, start: str, end: str, limit: int, verify_ssl: bool):
    """查询模式：POST /select/logsql/query"""
    url = urljoin(base_url.rstrip("/") + "/", "select/logsql/query")

    start_rfc = parse_time(start)
    end_rfc = parse_time(end)

    params = {
        "query": query,
        "start": start_rfc,
        "end": end_rfc,
        "limit": limit,
    }

    print(f"[INFO] 查询: {query}", file=sys.stderr)
    print(f"[INFO] 时间范围: {start_rfc} 到 {end_rfc}", file=sys.stderr)

    try:
        resp = requests.post(url, params=params, verify=verify_ssl, stream=True, timeout=30)
        resp.raise_for_status()

        count = 0
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                record = json.loads(line)
                count += 1
                yield record
            except json.JSONDecodeError as e:
                print(f"[WARN] 无法解析 JSON: {line[:100]} - {e}", file=sys.stderr)

        print(f"[INFO] 查询完成，共 {count} 条日志", file=sys.stderr)

    except requests.RequestException as e:
        print(f"[ERROR] 请求失败: {e}", file=sys.stderr)
        sys.exit(1)


def tail_logs(base_url: str, query: str, verify_ssl: bool):
    """追踪模式：GET /select/logsql/tail"""
    url = urljoin(base_url.rstrip("/") + "/", "select/logsql/tail")

    params = {"query": query}

    print(f"[INFO] 实时追踪: {query}", file=sys.stderr)
    print("[INFO] Ctrl+C 停止追踪", file=sys.stderr)

    try:
        resp = requests.get(
            url, params=params, verify=verify_ssl, stream=True, timeout=None
        )
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            try:
                record = json.loads(line)
                yield record
            except json.JSONDecodeError as e:
                print(f"[WARN] 无法解析 JSON: {line[:100]} - {e}", file=sys.stderr)

    except requests.RequestException as e:
        print(f"[ERROR] 请求失败: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INFO] 已停止追踪", file=sys.stderr)
        sys.exit(0)


def format_output(record: dict, fields: list) -> str:
    """格式化输出：若只有 _msg，直接输出；否则用 field=value 格式"""
    if fields == ["_msg"]:
        return record.get("_msg", "")

    parts = []
    for field in fields:
        value = record.get(field, "")
        parts.append(f"{field}={value}")

    return " ".join(parts)


def check_pod_exists(context: str, namespace: str, pod_name: str) -> bool:
    """检查 Pod 是否存在"""
    try:
        cmd = ["kubectl", "--context", context, "-n", namespace, "get", "pod", pod_name, "-o", "jsonpath={.metadata.name}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception as e:
        print(f"[WARN] 检查 Pod 失败: {e}", file=sys.stderr)
        return False


def get_pods_by_app(context: str, namespace: str, app: str) -> list:
    """获取指定应用的所有 Pod 列表"""
    try:
        cmd = ["kubectl", "--context", context, "-n", namespace, "get", "pod",
               "-l", f"app={app}", "-o", "jsonpath={.items[*].metadata.name}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split()
        return []
    except Exception as e:
        print(f"[WARN] 获取 Pod 列表失败: {e}", file=sys.stderr)
        return []


def kubectl_logs(context: str, namespace: str, pod_name: str, tail: bool,
                 container: str = None, tail_lines: int = None) -> bool:
    """使用 kubectl logs 获取日志"""
    cmd = ["kubectl", "--context", context, "-n", namespace, "logs", pod_name]

    if container:
        cmd.extend(["-c", container])

    if tail:
        cmd.append("-f")
    elif tail_lines:
        cmd.extend(["--tail", str(tail_lines)])

    try:
        print(f"[INFO] 使用 kubectl logs: {context}/{namespace}/{pod_name}", file=sys.stderr)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, bufsize=1)

        for line in proc.stdout:
            print(line.rstrip())

        return True
    except KeyboardInterrupt:
        proc.terminate()
        print("\n[INFO] 已停止追踪", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[WARN] kubectl logs 失败: {e}，降级到 Victoria Logs", file=sys.stderr)
        return False


def build_query(namespace: str, app: str = None, pod: str = None, extra_query: str = None) -> str:
    """构建 LogsQL 查询语句。

    - `--pod` 按 Pod 名精确匹配
    - `--app` 按工作负载名匹配 Pod 前缀，兼容 Deployment/StatefulSet 生成的 Pod 名
    """
    stream_filters = [f'namespace="{namespace}"']

    if app:
        stream_filters.append(f'pod=~"{app}.*"')
    elif pod:
        stream_filters.append(f'pod="{pod}"')

    query = f"_stream:{{{','.join(stream_filters)}}}"

    if extra_query:
        query = f"{query} {extra_query}"

    return query


def main():
    parser = argparse.ArgumentParser(
        description="日志查询工具（优先 kubectl logs，降级 Victoria Logs）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 按 namespace + app 查询（优先 kubectl logs）
  %(prog)s -n ske-model -a qwen3-embedding-8b -c ks

  # 按 namespace + pod 查询（优先 kubectl logs）
  %(prog)s -n ske-model -p llm-server-0 -c ks

  # 历史日志查询（无法获取 kubectl logs 时自动降级）
  %(prog)s -n ske -a resource-operator --filter '_msg:"error"' --start 2h

  # 实时追踪（Pod 存在则用 kubectl logs -f）
  %(prog)s -n ske-model -a qwen3-30b -c ks --tail

  # 只用 Victoria Logs（强制不用 kubectl）
  %(prog)s -n ske-model -a deepseek-r1-0528-8b --logs-only --start 3h --limit 50
        """,
    )

    parser.add_argument("-n", "--namespace", required=True, help="命名空间（必需）")
    parser.add_argument("-c", "--context", help="K8s context（不指定则不使用 kubectl）")

    filter_group = parser.add_mutually_exclusive_group(required=True)
    filter_group.add_argument("-a", "--app", help="应用名称（与 --pod 二选一）")
    filter_group.add_argument("-p", "--pod", help="Pod 名称（与 --app 二选一）")

    parser.add_argument(
        "--filter",
        help="额外的 LogsQL 过滤条件，如 '_msg:\"error\"' 或 'level:\"WARN\"'",
    )
    parser.add_argument(
        "--start", default="1h", help="开始时间 (相对: 1h/2d/30m, 绝对: RFC3339, 默认: 1h)"
    )
    parser.add_argument("--end", default="now", help="结束时间 (默认: now)")
    parser.add_argument("--limit", type=int, default=1000, help="最多返回条数 (默认: 1000)")
    parser.add_argument(
        "--tail",
        action="store_true",
        help="实时追踪模式，类似 tail -f (按 Ctrl+C 停止)",
    )
    parser.add_argument(
        "--fields",
        default="_msg",
        help="输出字段，逗号分隔 (默认: _msg，如: _time,_msg,pod,app)",
    )
    parser.add_argument(
        "--logs-only",
        action="store_true",
        help="只使用 Victoria Logs，不用 kubectl",
    )
    parser.add_argument(
        "--url",
        help="VictoriaLogs 服务地址（优先级高于 --context 自动选择）",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="跳过 SSL 验证 (用于自签证书)",
    )

    args = parser.parse_args()
    fields = [f.strip() for f in args.fields.split(",")]
    verify_ssl = not args.no_verify
    vl_url = resolve_vl_url(args.context, args.url)

    # 优先使用 kubectl logs
    used_kubectl = False
    if args.context and not args.logs_only:
        if args.pod:
            # 检查指定的 Pod 是否存在
            if check_pod_exists(args.context, args.namespace, args.pod):
                used_kubectl = kubectl_logs(args.context, args.namespace, args.pod, args.tail)
        else:
            # 获取应用对应的 Pod 列表
            pods = get_pods_by_app(args.context, args.namespace, args.app)
            if pods:
                if len(pods) == 1:
                    used_kubectl = kubectl_logs(args.context, args.namespace, pods[0], args.tail)
                else:
                    print(f"[INFO] 发现 {len(pods)} 个 Pod: {', '.join(pods)}", file=sys.stderr)
                    print(f"[INFO] 使用第一个 Pod: {pods[0]}", file=sys.stderr)
                    used_kubectl = kubectl_logs(args.context, args.namespace, pods[0], args.tail)

    # 降级到 Victoria Logs
    if not used_kubectl:
        query = build_query(args.namespace, args.app, args.pod, args.filter)

        try:
            if args.tail:
                records = tail_logs(vl_url, query, verify_ssl)
            else:
                records = query_logs(vl_url, query, args.start, args.end, args.limit, verify_ssl)

            for record in records:
                output = format_output(record, fields)
                if output:
                    print(output)

        except KeyboardInterrupt:
            print("\n[INFO] 已取消", file=sys.stderr)
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] 未知错误: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
