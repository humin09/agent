#!/usr/bin/env python3
import json
import subprocess
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import requests


OUTPUT_FILE = "~/agent/reports/available_models.md"
CLUSTERS = [
    {"name": "昆山", "context": "ks", "namespace": "ske-model"},
    {"name": "郑州", "context": "zz", "namespace": "ske-model"},
]
RESPONSES_TIMEOUT = 6
MAX_PROBE_WORKERS = 12


def get_k8s_resources(context, namespace):
    cmd = [
        "kubectl",
        "--context",
        context,
        "-n",
        namespace,
        "get",
        "deploy,svc,ingress,endpoints,pod",
        "-o",
        "json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting resources from {context}: {result.stderr}")
        return None
    return json.loads(result.stdout)


def probe_url(url, timeout=6, retries=2, retry_interval=1):
    for attempt in range(retries):
        try:
            return requests.get(url, timeout=timeout)
        except Exception:
            if attempt < retries - 1:
                time.sleep(retry_interval)
    return None


def probe_json_post(url, payload, timeout=5, headers=None, retries=1, retry_interval=1):
    for attempt in range(retries):
        try:
            return requests.post(url, json=payload, timeout=timeout, headers=headers)
        except Exception:
            if attempt < retries - 1:
                time.sleep(retry_interval)
    return None


def parse_json_response(response):
    if response is None:
        return None
    try:
        return response.json()
    except Exception:
        return None


def is_standard_response_object(data):
    return isinstance(data, dict) and data.get("object") == "response"


def probe_responses_basic(url_prefix, model_id):
    payload = {
        "model": model_id,
        "input": "你好，请用一句话介绍你自己",
        "max_output_tokens": 32,
    }
    response = probe_json_post(f"{url_prefix}/v1/responses", payload, timeout=RESPONSES_TIMEOUT)
    data = parse_json_response(response)
    return {
        "status_code": response.status_code if response is not None else None,
        "ok": response is not None and response.status_code == 200 and is_standard_response_object(data),
        "data": data,
    }


def probe_responses_tools(url_prefix, model_id):
    payload = {
        "model": model_id,
        "input": "北京天气如何？如果需要就调用工具。",
        "tools": [
            {
                "type": "function",
                "name": "get_weather",
                "description": "Get weather by city",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            }
        ],
        "tool_choice": "auto",
        "max_output_tokens": 64,
    }
    response = probe_json_post(f"{url_prefix}/v1/responses", payload, timeout=RESPONSES_TIMEOUT)
    data = parse_json_response(response)
    tools_echoed = isinstance(data, dict) and isinstance(data.get("tools"), list)
    parallel_tool_calls = isinstance(data, dict) and "parallel_tool_calls" in data
    return {
        "status_code": response.status_code if response is not None else None,
        "ok": response is not None and response.status_code == 200 and is_standard_response_object(data),
        "tools_echoed": tools_echoed,
        "parallel_tool_calls": parallel_tool_calls,
        "data": data,
    }


def is_subset(expected, actual):
    if not expected:
        return False
    return all(actual.get(k) == v for k, v in expected.items())


def base_name(host):
    return host.split(".", 1)[0] if host else ""


def host_sort_key(host, deploy_name):
    name = base_name(host)
    return (
        0 if name == deploy_name else 1,
        0 if name.startswith(deploy_name) else 1,
        len(name),
        name,
    )


def pick_primary_host(hosts, deploy_name):
    if not hosts:
        return None
    return sorted(hosts, key=lambda host: host_sort_key(host, deploy_name))[0]


def parse_resources(resources):
    deployments = {}
    services = {}
    ingresses = []
    endpoints = {}
    pods = {}

    for item in resources.get("items", []):
        kind = item.get("kind")
        metadata = item.get("metadata", {})
        name = metadata.get("name")

        if kind == "Deployment":
            deployments[name] = {
                "name": name,
                "replicas": item.get("spec", {}).get("replicas", 0),
                "available": item.get("status", {}).get("availableReplicas", 0),
                "selector": item.get("spec", {}).get("selector", {}).get("matchLabels", {}),
                "template_labels": item.get("spec", {})
                .get("template", {})
                .get("metadata", {})
                .get("labels", {}),
                "hosts": set(),
                "routes": [],
            }
        elif kind == "Service":
            services[name] = {
                "name": name,
                "selector": item.get("spec", {}).get("selector", {}) or {},
                "labels": metadata.get("labels", {}) or {},
            }
        elif kind == "Ingress":
            for rule in item.get("spec", {}).get("rules", []):
                host = rule.get("host")
                for path in rule.get("http", {}).get("paths", []):
                    svc_name = path.get("backend", {}).get("service", {}).get("name")
                    if host and svc_name:
                        ingresses.append(
                            {
                                "ingress_name": name,
                                "host": host,
                                "service_name": svc_name,
                            }
                        )
        elif kind == "Endpoints":
            pod_names = []
            for subset in item.get("subsets", []) or []:
                for address in subset.get("addresses", []) or []:
                    target_ref = address.get("targetRef", {}) or {}
                    if target_ref.get("kind") == "Pod" and target_ref.get("name"):
                        pod_names.append(target_ref["name"])
            endpoints[name] = pod_names
        elif kind == "Pod":
            pods[name] = metadata.get("labels", {}) or {}

    return deployments, services, ingresses, endpoints, pods


def match_deployments_by_pod_labels(pod_labels, deployments):
    matches = []
    for deploy in deployments.values():
        if is_subset(deploy["selector"], pod_labels):
            matches.append(deploy["name"])
    return matches


def match_deployments_by_service(service, deployments, pods):
    matches = set()
    selector = service.get("selector", {})

    if service["name"] in deployments:
        matches.add(service["name"])

    for deploy in deployments.values():
        if selector and (
            is_subset(selector, deploy["selector"])
            or is_subset(selector, deploy["template_labels"])
        ):
            matches.add(deploy["name"])

    if selector:
        for pod_labels in pods.values():
            if is_subset(selector, pod_labels):
                matches.update(match_deployments_by_pod_labels(pod_labels, deployments))

    matches.update(match_deployments_by_name_candidates(service, deployments))
    return sorted(matches)


def match_deployments_by_name_candidates(service, deployments):
    matches = set()
    selector = service.get("selector", {})
    labels = service.get("labels", {})

    name_candidates = {
        service["name"],
        labels.get("app"),
        labels.get("model"),
        selector.get("app"),
        selector.get("model"),
    }
    name_candidates = {candidate for candidate in name_candidates if candidate}

    for candidate in name_candidates:
        if candidate in deployments:
            matches.add(candidate)
        for suffix in ("-head-1", "-1"):
            alias = f"{candidate}{suffix}"
            if alias in deployments:
                matches.add(alias)

    return sorted(matches)


def build_service_records(deployments, services, ingresses, endpoints, pods):
    service_routes = {}
    for route in ingresses:
        service_routes.setdefault(route["service_name"], []).append(route)

    records = []
    matched_deployments = set()
    service_names = sorted(
        services,
        key=lambda name: (0 if service_routes.get(name) else 1, name),
    )

    for service_name in service_names:
        service = services[service_name]
        service_matched = set()

        for pod_name in endpoints.get(service_name, []):
            pod_labels = pods.get(pod_name, {})
            service_matched.update(match_deployments_by_pod_labels(pod_labels, deployments))

        if service_matched:
            # Head/worker 模式下，endpoints 往往只落到 head pod；
            # 这里仅按命名别名补全 worker deployment，避免把 sibling 服务串到一起。
            service_matched.update(match_deployments_by_name_candidates(service, deployments))
        else:
            service_matched.update(match_deployments_by_service(service, deployments, pods))

        routes = service_routes.get(service_name, [])
        if not routes and not service_matched:
            continue
        if not routes and service_matched.issubset(matched_deployments):
            continue

        matched_deployments.update(service_matched)
        sorted_deployments = sorted(service_matched)
        replicas = sum(deployments[name]["replicas"] for name in sorted_deployments)
        available = sum(deployments[name]["available"] for name in sorted_deployments)
        hosts = sorted(
            {route["host"] for route in routes},
            key=lambda host: host_sort_key(host, service_name),
        )

        records.append(
            {
                "name": service_name,
                "service_name": service_name,
                "deployment_names": sorted_deployments,
                "replicas": replicas,
                "available": available,
                "hosts": hosts,
            }
        )

    for deploy_name, deploy in deployments.items():
        if deploy_name in matched_deployments:
            continue
        records.append(
            {
                "name": deploy_name,
                "service_name": None,
                "deployment_names": [deploy_name],
                "replicas": deploy["replicas"],
                "available": deploy["available"],
                "hosts": [],
            }
        )

    records.sort(key=lambda item: item["name"])
    return records


def collect_cluster_data(cluster):
    resources = get_k8s_resources(cluster["context"], cluster["namespace"])
    if not resources:
        return {"records": []}

    deployments, services, ingresses, endpoints, pods = parse_resources(resources)
    records = build_service_records(deployments, services, ingresses, endpoints, pods)
    return {"records": records}


def probe_host_details(url_prefix):
    details = {
        "url_prefix": url_prefix,
        "models_ok": False,
        "models_status": None,
        "models": [],
        "first_model": "",
        "anthropic_supported": False,
        "anthropic_status": "未探测",
        "responses_supported": False,
        "responses_status": "未探测",
        "responses_multiturn_status": "示例，未实测",
        "responses_tools_supported": False,
        "responses_tools_status": "未探测",
    }

    model_response = probe_url(f"{url_prefix}/v1/models")
    if model_response is None:
        details["models_status"] = "Connection failed"
        return details

    details["models_status"] = model_response.status_code
    if model_response.status_code != 200:
        return details

    try:
        model_data = model_response.json()
    except Exception:
        details["models_status"] = "Invalid JSON"
        return details

    models = model_data.get("data", [])
    details["models_ok"] = True
    details["models"] = models
    if models:
        details["first_model"] = models[0].get("id", "")

    if details["first_model"]:
        anthropic_payload = {
            "model": details["first_model"],
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "你好"}],
            "stream": False,
        }
        anthropic_headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        with ThreadPoolExecutor(max_workers=2) as executor:
            anthropic_future = executor.submit(
                probe_json_post,
                f"{url_prefix}/v1/messages",
                anthropic_payload,
                5,
                anthropic_headers,
            )
            basic_future = executor.submit(
                probe_responses_basic,
                url_prefix,
                details["first_model"],
            )
            anthropic_response = anthropic_future.result()
            basic_probe = basic_future.result()

        if anthropic_response is not None and anthropic_response.status_code == 200:
            details["anthropic_supported"] = True
            details["anthropic_status"] = "✅"
        else:
            details["anthropic_status"] = "❌"

        if basic_probe["ok"]:
            details["responses_supported"] = True
            details["responses_status"] = "✅"

            tools_probe = probe_responses_tools(url_prefix, details["first_model"])
            if tools_probe["ok"] and (
                tools_probe["tools_echoed"] or tools_probe["parallel_tool_calls"]
            ):
                details["responses_tools_supported"] = True
                details["responses_tools_status"] = "✅"
            else:
                status_code = tools_probe["status_code"]
                details["responses_tools_status"] = (
                    f"❌({status_code})" if status_code is not None else "❌"
                )
        else:
            status_code = basic_probe["status_code"]
            details["responses_status"] = (
                f"❌({status_code})" if status_code is not None else "❌"
            )
            details["responses_tools_status"] = "未探测"

    return details


def render_host_probe(md, probe):
    url_prefix = probe["url_prefix"]
    if probe["models_ok"]:
        return md + f"- {url_prefix}:/v1/models ✅\n"
    return md + f"- {url_prefix}:/v1/models ❌\n"


def generate_markdown(clusters_data):
    md = ""

    for _, data in clusters_data.items():
        if not data["records"]:
            continue

        for record in data["records"]:
            md += f"### {record['name']}\n"

            if not record["hosts"]:
                md += "- /v1/models ❌\n"
                md += f"- 副本数{record['replicas']}/{record['available']}\n\n"
                continue

            with ThreadPoolExecutor(
                max_workers=min(len(record["hosts"]), MAX_PROBE_WORKERS)
            ) as executor:
                probes = list(
                    executor.map(
                        lambda host: probe_host_details(f"http://{host}:58000"),
                        record["hosts"],
                    )
                )

            primary_host = pick_primary_host(record["hosts"], record["name"])
            primary_probe = None
            if primary_host:
                primary_url = f"http://{primary_host}:58000"
                primary_probe = next(
                    (probe for probe in probes if probe["url_prefix"] == primary_url),
                    None,
                )

            successful_probe = next((probe for probe in probes if probe["models_ok"]), primary_probe)
            if successful_probe and successful_probe["models_ok"]:
                md = render_host_probe(md, successful_probe)
                md += f"- Anthropic 协议: {successful_probe['anthropic_status']}\n"
                md += f"- OpenAI Responses 协议: {successful_probe['responses_status']}\n"
                md += f"- Responses 多轮对话: {successful_probe['responses_multiturn_status']}\n"
                md += f"- Responses 工具调用: {successful_probe['responses_tools_status']}\n"
                first_model = successful_probe["first_model"]
                first_max_len = "N/A"
                if successful_probe["models"]:
                    first_max_len = successful_probe["models"][0].get("max_model_len", "N/A")
                md += f"- 模型信息: {first_model}\n"
                md += f"- 模型最大上下文长度: {first_max_len}\n"
                md += f"- 副本数{record['replicas']}/{record['available']}\n"
                if first_model:
                    md += "请求示例:\n"
                    md += "```bash\n"
                    md += f"curl -X POST '{successful_probe['url_prefix']}/v1/chat/completions' \\\n"
                    md += "  -H 'Content-Type: application/json' \\\n"
                    md += "  -d '{\n"
                    md += f'    "model": "{first_model}",\n'
                    md += '    "messages": [{"role": "user", "content": "你好"}],\n'
                    md += '    "temperature": 0.7,\n'
                    md += '    "stream": false\n'
                    md += "  }'\n"
                    md += "```\n"
                    if successful_probe["responses_supported"]:
                        md += "OpenAI Responses 示例:\n"
                        md += "```bash\n"
                        md += f"curl -X POST '{successful_probe['url_prefix']}/v1/responses' \\\n"
                        md += "  -H 'Content-Type: application/json' \\\n"
                        md += "  -d '{\n"
                        md += f'    "model": "{first_model}",\n'
                        md += '    "input": "你好，请用一句话介绍你自己",\n'
                        md += '    "max_output_tokens": 128\n'
                        md += "  }'\n"
                        md += "```\n"
                        md += "OpenAI Responses 多轮示例:\n"
                        md += "```bash\n"
                        md += f"curl -X POST '{successful_probe['url_prefix']}/v1/responses' \\\n"
                        md += "  -H 'Content-Type: application/json' \\\n"
                        md += "  -d '{\n"
                        md += f'    "model": "{first_model}",\n'
                        md += '    "previous_response_id": "<上一轮返回的 id>",\n'
                        md += '    "input": "继续展开上一轮回答",\n'
                        md += '    "max_output_tokens": 128\n'
                        md += "  }'\n"
                        md += "```\n"
                        if successful_probe["responses_tools_supported"]:
                            md += "OpenAI Responses 工具调用示例:\n"
                            md += "```bash\n"
                            md += f"curl -X POST '{successful_probe['url_prefix']}/v1/responses' \\\n"
                            md += "  -H 'Content-Type: application/json' \\\n"
                            md += "  -d '{\n"
                            md += f'    "model": "{first_model}",\n'
                            md += '    "input": "北京天气如何？如果需要就调用工具。",\n'
                            md += '    "tool_choice": "auto",\n'
                            md += '    "tools": [\n'
                            md += '      {\n'
                            md += '        "type": "function",\n'
                            md += '        "name": "get_weather",\n'
                            md += '        "description": "Get weather by city",\n'
                            md += '        "parameters": {\n'
                            md += '          "type": "object",\n'
                            md += '          "properties": {\n'
                            md += '            "city": {"type": "string"}\n'
                            md += '          },\n'
                            md += '          "required": ["city"]\n'
                            md += '        }\n'
                            md += '      }\n'
                            md += '    ],\n'
                            md += '    "max_output_tokens": 128\n'
                            md += "  }'\n"
                            md += "```\n"
            else:
                fallback_probe = primary_probe or probes[0]
                md = render_host_probe(md, fallback_probe)
                md += "- Anthropic 协议: ❌\n"
                md += f"- OpenAI Responses 协议: {fallback_probe['responses_status']}\n"
                md += "- Responses 多轮对话: 示例，未实测\n"
                md += f"- Responses 工具调用: {fallback_probe['responses_tools_status']}\n"
                md += "- 模型信息: ❌\n"
                md += "- 模型最大上下文长度: N/A\n"
                md += f"- 副本数{record['replicas']}/{record['available']}\n"

            md += "\n"

    return md


def main():
    clusters_data = {}
    for cluster in CLUSTERS:
        clusters_data[cluster["name"]] = collect_cluster_data(cluster)

    markdown = generate_markdown(clusters_data)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file_obj:
        file_obj.write(markdown)

    print(f"报告已生成: {OUTPUT_FILE}")
    print("\n" + markdown)


if __name__ == "__main__":
    main()
