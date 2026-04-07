#!/usr/bin/env python3
import subprocess
import requests
import json
from datetime import datetime
import time


def get_k8s_resources(context, namespace):
    cmd = [
        "kubectl",
        "--context",
        context,
        "-n",
        namespace,
        "get",
        "deploy,svc,ingress",
        "-o",
        "json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting resources from {context}: {result.stderr}")
        return None
    return json.loads(result.stdout)


def probe_url(url, timeout=10):
    try:
        response = requests.get(url, timeout=timeout)
        return response
    except Exception as e:
        return None


def generate_markdown(clusters_data):
    md = f"# ske-model 可用模型列表\n"
    md += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    for cluster_name, data in clusters_data.items():
        md += f"## {cluster_name} 集群\n\n"

        if not data["deployments"]:
            md += "暂无 deployment 资源\n\n"
            continue

        for deploy in data["deployments"]:
            md += f"### {deploy['name']}\n"
            md += f"- 副本数: {deploy['replicas']}/{deploy['available']}\n"

            if deploy["host"]:
                host = deploy["host"]
                url_prefix = f"http://{host}:58000"

                md += f"- 访问地址: `{url_prefix}`\n"

                model_response = probe_url(f"{url_prefix}/v1/models")
                if model_response and model_response.status_code == 200:
                    try:
                        model_data = model_response.json()
                        md += f"- 模型信息:\n"
                        for model in model_data.get("data", []):
                            model_id = model["id"]
                            md += f"  - `{model_id}`\n"
                            md += f"    - 最大上下文长度: {model.get('max_model_len', 'N/A')}\n"

                        md += f"\n#### 验证过的 curl 命令:\n"
                        md += f"**获取模型列表:**\n"
                        md += f"```bash\n"
                        md += f"curl -s {url_prefix}/v1/models\n"
                        md += f"```\n"

                        first_model = model_data.get("data", [{}])[0].get("id", "")
                        if first_model:
                            md += f"\n**Chat Completions 测试:**\n"
                            md += f"```bash\n"
                            md += (
                                f"curl -X POST '{url_prefix}/v1/chat/completions' \\\n"
                            )
                            md += f"  -H 'Content-Type: application/json' \\\n"
                            md += f"  -d '{{\n"
                            md += f'    "model": "{first_model}",\n'
                            md += f'    "messages": [{{"role": "user", "content": "你好"}}],\n'
                            md += f'    "temperature": 0.7,\n'
                            md += f'    "stream": false\n'
                            md += f"  }}'\n"
                            md += f"```\n"
                    except:
                        md += f"- 模型信息: ❌ 无法解析响应\n"
                else:
                    status_code = (
                        model_response.status_code
                        if model_response
                        else "Connection failed"
                    )
                    md += f"- 模型信息: ❌ 无法访问 (HTTP {status_code})\n"
            else:
                md += f"- 模型信息: ❌ 无对应 ingress\n"

            md += "\n"

    return md


def main():
    clusters = [
        {"name": "昆山", "context": "ks", "namespace": "ske-model"},
        {"name": "郑州", "context": "zz", "namespace": "ske-model"},
    ]

    clusters_data = {}

    for cluster in clusters:
        resources = get_k8s_resources(cluster["context"], cluster["namespace"])
        if not resources:
            continue

        deployments = {}
        services = {}
        ingresses = []

        for item in resources.get("items", []):
            if item.get("kind") == "Deployment":
                name = item["metadata"]["name"]
                replicas = item.get("spec", {}).get("replicas", 0)
                available = item.get("status", {}).get("availableReplicas", 0)
                selector = (
                    item.get("spec", {}).get("selector", {}).get("matchLabels", {})
                )
                deployments[name] = {
                    "name": name,
                    "replicas": replicas,
                    "available": available,
                    "selector": selector,
                    "host": None,
                }
            elif item.get("kind") == "Service":
                name = item["metadata"]["name"]
                selector = item.get("spec", {}).get("selector", {})
                services[name] = selector
            elif item.get("kind") == "Ingress":
                for rule in item.get("spec", {}).get("rules", []):
                    host = rule.get("host")
                    if host:
                        for path in rule.get("http", {}).get("paths", []):
                            svc_name = (
                                path.get("backend", {}).get("service", {}).get("name")
                            )
                            if svc_name:
                                ingresses.append(
                                    {"host": host, "service_name": svc_name}
                                )

        for ingress in ingresses:
            svc_name = ingress["service_name"]
            if svc_name in services:
                svc_selector = services[svc_name]
                for deploy_name, deploy in deployments.items():
                    deploy_selector = deploy["selector"]
                    match = True
                    for k, v in svc_selector.items():
                        if deploy_selector.get(k) != v:
                            match = False
                            break
                    if match:
                        deployments[deploy_name]["host"] = ingress["host"]

        clusters_data[cluster["name"]] = {"deployments": list(deployments.values())}

    markdown = generate_markdown(clusters_data)

    output_file = "/Users/humin/.config/opencode/skills/maas/available_models.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"报告已生成: {output_file}")
    print("\n" + markdown)


if __name__ == "__main__":
    main()
