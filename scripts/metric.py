#!/usr/bin/env python3
"""Prometheus/Thanos 监控指标查询工具"""

import requests
import json
import datetime
import time
import argparse
import sys
import fnmatch
import urllib.parse
from typing import Optional, Dict, List, Any, Callable

requests.packages.urllib3.disable_warnings()

CLUSTERS = {
    "dz": ("达州", "生产"),
    "ks": ("昆山", "生产"),
    "wh": ("武汉", "生产"),
    "sz": ("深圳", "生产"),
    "qd": ("青岛", "生产"),
    "bj": ("北京", "测试"),
    "sh": ("上海", "测试"),
    "ly": ("洛阳", "测试"),
    "wq": ("魏桥", "生产"),
    "zz": ("郑州", "生产"),
    "ny": ("纽约", "生产"),
}

CLUSTER_URLS = {
    code: f"https://mertric.{code}ai.scnet.cn:58043/select/0/prometheus/api/v1/query"
    for code in CLUSTERS.keys()
}
CLUSTER_URLS["zz"] = "https://mertric.zzai2.scnet.cn:58043/select/0/prometheus/api/v1/query"


def get_cluster_url(cluster: str) -> str:
    """获取集群对应的 Prometheus URL"""
    cluster = cluster.lower()
    if cluster not in CLUSTER_URLS:
        raise ValueError(f"无效集群: {cluster}")
    return CLUSTER_URLS[cluster]


class MetricClient:
    def __init__(self, cluster: str = "dz"):
        """初始化 Prometheus 客户端"""
        self.base_url = get_cluster_url(cluster).rstrip("/")
        self.session = requests.Session()
        self.session.verify = False

    def _safe_request(self, endpoint: str, params: Dict = None, error_msg: str = "请求失败") -> Optional[Dict]:
        """统一的 HTTP 请求处理"""
        try:
            response = self.session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"{error_msg}: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"  状态码: {e.response.status_code}")
                if e.response.text and len(e.response.text) < 500:
                    print(f"  响应: {e.response.text[:200]}")
            return None

    def query(self, promql: str, query_time: Optional[float] = None) -> Optional[Dict]:
        """执行 PromQL 即时查询"""
        params = {
            "query": promql,
            "time": query_time or time.time(),
            "dedup": "true",
            "partial_response": "true",
        }
        return self._safe_request(f"{self.base_url}/api/v1/query", params, "查询失败")

    def query_range(self, promql: str, start: float, end: float, step: str) -> Optional[Dict]:
        """执行 PromQL 范围查询"""
        params = {
            "query": promql,
            "start": start,
            "end": end,
            "step": step,
            "dedup": "true",
            "partial_response": "true",
        }
        return self._safe_request(f"{self.base_url}/api/v1/query_range", params, "范围查询失败")

    def format_result(self, data: Optional[Dict]) -> List[str]:
        """格式化查询结果"""
        if not data or data.get("status") != "success":
            return [f"查询失败: {data.get('error', '未知错误') if data else '无响应'}"]

        result = data.get("data", {})
        result_type = result.get("resultType")
        values = result.get("result", [])

        if not values:
            return ["未找到数据"]

        lines = []
        dt_fmt = "%Y-%m-%d %H:%M:%S"

        if result_type == "vector":
            for item in values:
                metric = item.get("metric", {})
                ts, val = item.get("value", [0, "0"])
                time_str = datetime.datetime.fromtimestamp(float(ts)).strftime(dt_fmt)
                labels = ", ".join(f"{k}={v}" for k, v in metric.items())
                lines.append(f"[{time_str}] {labels} → {val}")

        elif result_type == "matrix":
            for item in values:
                metric = item.get("metric", {})
                labels = ", ".join(f"{k}={v}" for k, v in metric.items())
                lines.append(f"指标: {labels}")
                for ts, val in item.get("values", []):
                    time_str = datetime.datetime.fromtimestamp(float(ts)).strftime(dt_fmt)
                    lines.append(f"  [{time_str}] → {val}")
                lines.append("")

        elif result_type in ("scalar", "string"):
            ts, val = result.get("result", [0, "0"])
            time_str = datetime.datetime.fromtimestamp(float(ts)).strftime(dt_fmt)
            lines.append(f"[{time_str}] {val}")

        return lines

    def get_metrics(self) -> List[str]:
        """获取所有指标名称"""
        result = self._safe_request(f"{self.base_url}/api/v1/label/__name__/values", error_msg="获取指标列表失败")
        return result.get("data", []) if result and result.get("status") == "success" else []

    def get_labels(self) -> List[str]:
        """获取所有标签名称"""
        result = self._safe_request(f"{self.base_url}/api/v1/labels", error_msg="获取标签列表失败")
        return result.get("data", []) if result and result.get("status") == "success" else []

    def get_label_values(self, label: str) -> List[str]:
        """获取指定标签的所有值"""
        endpoint = f"{self.base_url}/api/v1/label/{urllib.parse.quote(label)}/values"
        result = self._safe_request(endpoint, error_msg=f"获取标签值失败")
        return result.get("data", []) if result and result.get("status") == "success" else []


def parse_time(time_str: str) -> datetime.datetime:
    """解析时间字符串，支持多种格式"""
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(time_str, fmt)
        except ValueError:
            pass
    raise ValueError(f"无法解析时间: {time_str}")


def parse_time_range(start_str: Optional[str], end_str: Optional[str], range_str: str) -> tuple:
    """解析时间范围，返回 (start_time, end_time) Unix 时间戳"""
    now = datetime.datetime.now()
    end_time = time.mktime(now.timetuple())

    if start_str and end_str:
        start_time = time.mktime(parse_time(start_str).timetuple())
        end_time = time.mktime(parse_time(end_str).timetuple())
    else:
        # 解析相对时间范围
        match = ""
        for i, c in enumerate(range_str[::-1]):
            if c.isdigit():
                match = c + match
            else:
                unit = range_str[len(range_str) - i - 1:]
                break

        if not match:
            raise ValueError(f"无效的时间范围: {range_str}")

        delta_map = {"h": datetime.timedelta(hours=int(match)), "d": datetime.timedelta(days=int(match)), "m": datetime.timedelta(minutes=int(match))}
        delta = delta_map.get(unit)
        if not delta:
            raise ValueError(f"无效的时间单位: {unit}")

        start_dt = now - delta
        start_time = time.mktime(start_dt.timetuple())

    return start_time, end_time


def get_cluster_help() -> str:
    """生成集群列表帮助信息"""
    lines = []
    for code, (city, env) in CLUSTERS.items():
        lines.append(f"  {code}: {city} ({env})")
    return "\n".join(lines)


def main():
    cluster_help = get_cluster_help()
    parser = argparse.ArgumentParser(
        prog="metric",
        description="Prometheus/Thanos 监控指标查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
示例:
  # 即时查询
  metric query -c ks -q "kube_node_info"
  metric query -c dz -q "sum(rate(node_cpu_seconds_total{{mode='idle'}}[5m])) by (instance)"

  # 范围查询
  metric range -c wh -q "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes" \\
    --start "2024-01-01 00:00:00" --end "2024-01-01 01:00:00" --step "1m"
  metric range -c sz -q "rate(node_cpu_seconds_total[5m])" --range "1h" --step "5m"

  # 获取指标和标签
  metric metrics -c dz
  metric metrics -c ks -p "kube_*"
  metric labels -c wh
  metric label-values -c sz -l "instance"

支持集群:
{cluster_help}
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")
    cluster_choices = list(CLUSTER_URLS.keys())

    # query 子命令
    query = subparsers.add_parser("query", help="即时查询 (PromQL)")
    query.add_argument("-c", "--cluster", default="dz", choices=cluster_choices, help="集群 (默认: dz)")
    query.add_argument("-q", "--query", required=True, help="PromQL 查询语句")
    query.add_argument("-t", "--time", help="查询时间 (YYYY-MM-DD HH:MM:SS)")

    # range 子命令
    range_cmd = subparsers.add_parser("range", help="范围查询 (PromQL)")
    range_cmd.add_argument("-c", "--cluster", default="dz", choices=cluster_choices, help="集群 (默认: dz)")
    range_cmd.add_argument("-q", "--query", required=True, help="PromQL 查询语句")
    range_cmd.add_argument("--start", help="开始时间 (YYYY-MM-DD HH:MM:SS)")
    range_cmd.add_argument("--end", help="结束时间 (YYYY-MM-DD HH:MM:SS)")
    range_cmd.add_argument("--range", default="1h", help="相对时间范围 (默认: 1h)")
    range_cmd.add_argument("--step", default="1m", help="查询步长 (默认: 1m)")

    # metrics 子命令
    metrics = subparsers.add_parser("metrics", help="列出所有指标")
    metrics.add_argument("-c", "--cluster", default="dz", choices=cluster_choices, help="集群 (默认: dz)")
    metrics.add_argument("-p", "--pattern", help="过滤模式 (支持通配符)")

    # labels 子命令
    labels = subparsers.add_parser("labels", help="列出所有标签")
    labels.add_argument("-c", "--cluster", default="dz", choices=cluster_choices, help="集群 (默认: dz)")

    # label-values 子命令
    label_values = subparsers.add_parser("label-values", help="列出指定标签的值")
    label_values.add_argument("-c", "--cluster", default="dz", choices=cluster_choices, help="集群 (默认: dz)")
    label_values.add_argument("-l", "--label", required=True, help="标签名称")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        client = MetricClient(args.cluster)

        if args.command == "query":
            query_time = time.mktime(parse_time(args.time).timetuple()) if args.time else None
            print(f"集群: {args.cluster} | 查询: {args.query}")
            result = client.query(args.query, query_time=query_time)
            for line in client.format_result(result):
                print(line)

        elif args.command == "range":
            start_time, end_time = parse_time_range(args.start, args.end, args.range)
            start_str = datetime.datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S")
            end_str = datetime.datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S")
            print(f"集群: {args.cluster} | 范围: {start_str} ~ {end_str} | 步长: {args.step}")
            result = client.query_range(args.query, start=start_time, end=end_time, step=args.step)
            for line in client.format_result(result):
                print(line)

        elif args.command == "metrics":
            metrics = client.get_metrics()
            if args.pattern:
                metrics = [m for m in metrics if fnmatch.fnmatch(m, args.pattern)]
            print(f"集群: {args.cluster} | 指标: {len(metrics)} 个" + (f" (模式: {args.pattern})" if args.pattern else ""))
            for m in sorted(metrics):
                print(f"  {m}")

        elif args.command == "labels":
            labels = client.get_labels()
            print(f"集群: {args.cluster} | 标签: {len(labels)} 个")
            for label in sorted(labels):
                print(f"  {label}")

        elif args.command == "label-values":
            values = client.get_label_values(args.label)
            print(f"集群: {args.cluster} | 标签 '{args.label}': {len(values)} 个")
            for v in sorted(values):
                print(f"  {v}")

    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"异常: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
