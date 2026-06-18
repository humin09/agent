#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OUTPUT_FILE = os.path.expanduser("~/agent/reports/available_models.md")
FEISHU_DOC = "Wab0dqBUto5NFixdPzWc0rGWnYg"
CLUSTERS = [
    {"name": "昆山", "context": "ks", "namespace": "ske-model"},
    {"name": "郑州", "context": "zz", "namespace": "ske-model"},
    {"name": "纽约", "context": "ny", "namespace": "ske-model"},
]
MAX_PROBE_WORKERS = 6
LIVENESS_TIMEOUT_SECONDS = 6
PROBE_TIMEOUT_SECONDS = 60
PROTOCOLS = ["chat_completions", "responses", "anthropic_messages"]
CAPABILITY_KEYS = [
    "basic",
    "stream",
    "usage",
    "tool_calls",
    "json_output",
    "structured_output",
    "prefix_cache_usage",
    "error_format",
]
TEST_KEYS = [
    "basic",
    "stream",
    "json_output",
    "structured_output",
    "tool_calling",
    "prefix_cache_usage",
    "error_format",
]


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


def probe_service(
    *,
    base_url: str,
    model: str,
    protocols: list[str] | tuple[str, ...] | None = None,
    output_tokens: int = 128,
    temperature: float = 0.0,
    request_timeout_seconds: int = 120,
    api_key: str | None = None,
    auth_type: str = "bearer",
    api_key_header: str = "X-API-Key",
) -> dict[str, Any]:
    args = {
        "base_url": base_url.rstrip("/"),
        "model": model,
        "output_tokens": output_tokens,
        "temperature": temperature,
        "request_timeout_seconds": request_timeout_seconds,
        "api_key": api_key,
        "auth_type": auth_type,
        "api_key_header": api_key_header,
    }
    headers = build_headers(args)
    protocols = list(protocols or PROTOCOLS)
    results: dict[str, Any] = {}
    print("[probe] Starting protocol probe...")
    if "chat_completions" in protocols:
        results["chat_completions"] = probe_protocol(args, "/v1/chat/completions", "chat", headers)
    if "responses" in protocols:
        results["responses"] = probe_protocol(args, "/v1/responses", "responses", headers)
    if "anthropic_messages" in protocols:
        results["anthropic_messages"] = probe_protocol(args, "/v1/messages", "anthropic", headers)
    return {
        "type": "probe",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": {"mode": "k8s-service", "base_url": args["base_url"]},
        "model": {"name": model, "base_url": args["base_url"], "model_id": model},
        "summary": {
            "chat_completions_supported": bool(results.get("chat_completions", {}).get("supported")),
            "responses_supported": bool(results.get("responses", {}).get("supported")),
            "anthropic_messages_supported": bool(results.get("anthropic_messages", {}).get("supported")),
        },
        "protocols": results,
    }


def probe_protocol(args: dict[str, Any], endpoint: str, kind: str, headers: dict[str, str]) -> dict[str, Any]:
    url = base_url(args) + endpoint
    print(f"[probe] Testing {kind}: {url}")
    capabilities = {key: False for key in CAPABILITY_KEYS}
    tests: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []

    basic_payload = payload_for(kind, args, "Please briefly introduce yourself.", stream=False)
    basic = post_json(url, basic_payload, args["request_timeout_seconds"], headers)
    basic_ok = bool(basic.get("ok"))
    capabilities["basic"] = basic_ok
    capabilities["usage"] = has_usage(basic.get("json"))
    tests["basic"] = non_stream_test("basic", basic_payload, basic, basic_ok)
    log_capability("basic request", basic_ok, basic)
    if not basic_ok:
        errors.append({"capability": "basic", **classify_error(basic)})
        for name in ["stream", "json_output", "structured_output", "tool_calling", "prefix_cache_usage"]:
            tests[name] = skipped_test(name, {}, "basic request failed")
        error_payload = error_payload_for(kind, args)
        tests["error_format"] = non_stream_test("error_format", error_payload, basic, has_error_format(basic))
        return protocol_result(endpoint, False, basic.get("status_code"), capabilities, tests, errors)

    stream_payload = payload_for(kind, args, "Please briefly introduce yourself.", stream=True)
    stream = post_json_stream(url, stream_payload, args["request_timeout_seconds"], headers)
    capabilities["stream"] = bool(stream.get("ok"))
    tests["stream"] = stream_test("stream", stream_payload, stream)
    log_capability("stream request", capabilities["stream"], stream)
    if not stream.get("ok"):
        errors.append({"capability": "stream", **classify_error(stream)})

    json_payload = json_payload_for(kind, args)
    json_result = post_json(url, json_payload, args["request_timeout_seconds"], headers)
    capabilities["json_output"] = bool(json_result.get("ok"))
    tests["json_output"] = non_stream_test("json_output", json_payload, json_result, capabilities["json_output"])
    log_capability("json output", capabilities["json_output"], json_result)
    if not json_result.get("ok"):
        errors.append({"capability": "json_output", **classify_error(json_result)})

    structured_payload = structured_payload_for(kind, args)
    structured_result = post_json(url, structured_payload, args["request_timeout_seconds"], headers)
    capabilities["structured_output"] = bool(structured_result.get("ok"))
    tests["structured_output"] = non_stream_test("structured_output", structured_payload, structured_result, capabilities["structured_output"])
    log_capability("structured output", capabilities["structured_output"], structured_result)
    if not structured_result.get("ok"):
        errors.append({"capability": "structured_output", **classify_error(structured_result)})

    tool_payload = tool_payload_for(kind, args)
    tool_result = post_json(url, tool_payload, args["request_timeout_seconds"], headers)
    capabilities["tool_calls"] = bool(tool_result.get("ok") and has_tool_call(tool_result.get("json")))
    tests["tool_calling"] = non_stream_test("tool_calling", tool_payload, tool_result, capabilities["tool_calls"])
    log_capability("tool calling", capabilities["tool_calls"], tool_result)
    if not capabilities["tool_calls"]:
        errors.append({"capability": "tool_calling", **classify_error(tool_result)})

    prefix_payloads = prefix_cache_payloads_for(kind, args)
    prefix_result = probe_prefix_cache(url, prefix_payloads, args["request_timeout_seconds"], headers)
    capabilities["prefix_cache_usage"] = bool(prefix_result.get("ok"))
    tests["prefix_cache_usage"] = prefix_cache_test("prefix_cache_usage", prefix_payloads, prefix_result)
    log_capability("prefix cache usage", capabilities["prefix_cache_usage"], prefix_result)
    if not capabilities["prefix_cache_usage"]:
        errors.append({"capability": "prefix_cache_usage", **classify_error(prefix_result)})

    err_payload = error_payload_for(kind, args)
    err_result = post_json(url, err_payload, args["request_timeout_seconds"], headers)
    capabilities["error_format"] = has_error_format(err_result)
    tests["error_format"] = non_stream_test("error_format", err_payload, err_result, capabilities["error_format"])
    log_capability("error format", capabilities["error_format"], err_result)
    if not capabilities["error_format"]:
        errors.append({"capability": "error_format", **classify_error(err_result)})

    return protocol_result(endpoint, True, basic.get("status_code"), capabilities, tests, errors)


def base_url(args: dict[str, Any]) -> str:
    return str(args.get("base_url", "")).rstrip("/")


def build_headers(args: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    api_key = args.get("api_key")
    if api_key:
        if args.get("auth_type") == "bearer":
            headers["Authorization"] = f"Bearer {api_key}"
        elif args.get("auth_type") == "custom_header":
            headers[str(args.get("api_key_header") or "X-API-Key")] = api_key
    return headers


def post_json(url: str, payload: dict[str, Any], timeout: int, headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            parsed = _loads_or_none(text)
            return {"ok": 200 <= response.status < 300, "status_code": response.status, "json": parsed, "text": text, "error": None}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status_code": exc.code, "json": _loads_or_none(text), "text": text, "error": f"HTTP {exc.code}"}
    except Exception as exc:
        return {"ok": False, "status_code": None, "json": None, "text": "", "error": str(exc)}


def post_json_stream(url: str, payload: dict[str, Any], timeout: int, headers: dict[str, str], max_chunks: int = 5) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    chunks: list[Any] = []
    first_chunk: Any = None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                parsed = _loads_or_text(line)
                if first_chunk is None:
                    first_chunk = parsed
                chunks.append(parsed)
                if len(chunks) >= max_chunks:
                    break
            return {"ok": 200 <= response.status < 300, "status_code": response.status, "first_chunk": first_chunk, "chunks_sample": chunks, "error": None}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status_code": exc.code, "first_chunk": None, "chunks_sample": [], "error": f"HTTP {exc.code}: {text[:300]}"}
    except Exception as exc:
        return {"ok": False, "status_code": None, "first_chunk": None, "chunks_sample": [], "error": str(exc)}


def payload_for(kind: str, args: dict[str, Any], content: str, stream: bool) -> dict[str, Any]:
    if kind == "responses":
        payload: dict[str, Any] = {"model": args["model"], "input": content, "temperature": args["temperature"]}
        if args["output_tokens"]:
            payload["max_output_tokens"] = args["output_tokens"]
        if stream:
            payload["stream"] = True
        return payload
    if kind == "anthropic":
        payload = {"model": args["model"], "messages": [{"role": "user", "content": content}], "max_tokens": args["output_tokens"]}
        if stream:
            payload["stream"] = True
        return payload
    return {"model": args["model"], "messages": [{"role": "user", "content": content}], "temperature": args["temperature"], "max_tokens": args["output_tokens"], "stream": stream}


def json_payload_for(kind: str, args: dict[str, Any]) -> dict[str, Any]:
    payload = payload_for(kind, args, 'Return JSON only: {"name":"test","ok":true}', False)
    if kind == "chat":
        payload["response_format"] = {"type": "json_object"}
    elif kind == "responses":
        payload["text"] = {"format": {"type": "json_object"}}
    return payload


def structured_payload_for(kind: str, args: dict[str, Any]) -> dict[str, Any]:
    payload = payload_for(kind, args, "Return a JSON object with fields name and ok.", False)
    schema = {"type": "object", "properties": {"name": {"type": "string"}, "ok": {"type": "boolean"}}, "required": ["name", "ok"], "additionalProperties": False}
    if kind == "chat":
        payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "probe_schema", "schema": schema}}
    elif kind == "responses":
        payload["text"] = {"format": {"type": "json_schema", "name": "probe_schema", "schema": schema}}
    return payload


def tool_payload_for(kind: str, args: dict[str, Any]) -> dict[str, Any]:
    payload = payload_for(kind, args, "Call the tool to get the weather in Beijing.", False)
    schema = {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}
    if kind == "anthropic":
        payload["tools"] = [{"name": "get_weather", "description": "Get city weather", "input_schema": schema}]
    elif kind == "responses":
        payload["tools"] = [{"type": "function", "name": "get_weather", "description": "Get city weather", "parameters": schema}]
    else:
        payload["tools"] = [{"type": "function", "function": {"name": "get_weather", "description": "Get city weather", "parameters": schema}}]
    return payload


def prefix_cache_payloads_for(kind: str, args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    prefix = "\n".join(
        [
            "This is a shared long prefix for testing prefix-cache usage. The probe sends repeated requests with the same prefix so we can observe whether the second response includes usage.prompt_tokens_details.cached_tokens."
            for _ in range(32)
        ]
    )
    return (
        payload_for(kind, args, prefix + "\nQuestion one: Reply with exactly: first round.", False),
        payload_for(kind, args, prefix + "\nQuestion two: Reply with exactly: second round.", False),
    )


def error_payload_for(kind: str, args: dict[str, Any]) -> dict[str, Any]:
    if kind == "anthropic":
        return {"model": args["model"], "max_tokens": args["output_tokens"]}
    return {"model": args["model"]}


def probe_prefix_cache(url: str, payloads: tuple[dict[str, Any], dict[str, Any]], timeout: int, headers: dict[str, str]) -> dict[str, Any]:
    first = post_json(url, payloads[0], timeout, headers)
    second = post_json(url, payloads[1], timeout, headers)
    cached_tokens = safe_get(second.get("json"), "usage", "prompt_tokens_details", "cached_tokens")
    ok = bool(first.get("ok") and second.get("ok") and cached_tokens is not None)
    return {
        "ok": ok,
        "status_code": second.get("status_code") if second.get("status_code") is not None else first.get("status_code"),
        "first": first,
        "second": second,
        "cached_tokens": cached_tokens,
        "error": None if ok else second.get("error") or first.get("error") or "missing usage.prompt_tokens_details.cached_tokens",
    }


def protocol_result(endpoint: str, supported: bool, status_code: Any, capabilities: dict[str, bool], tests: dict[str, Any], errors: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "supported": supported,
        "status_code": status_code,
        "capabilities": capabilities,
        "tests": {key: tests.get(key, skipped_test(key, {}, "not run")) for key in TEST_KEYS},
        "errors": errors,
    }


def non_stream_test(name: str, request_body: dict[str, Any], result: dict[str, Any], supported: bool) -> dict[str, Any]:
    return {
        "name": name,
        "supported": supported,
        "status_code": result.get("status_code"),
        "request_body": request_body,
        "response_format": response_format(result.get("json")),
        "response_sample": truncate_value(result.get("json")) if result.get("ok") else None,
        "error_sample": None if result.get("ok") else truncate_value(error_sample(result)),
        "error": result.get("error"),
    }


def stream_test(name: str, request_body: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "supported": bool(result.get("ok")), "status_code": result.get("status_code"), "request_body": request_body, "first_chunk": truncate_value(result.get("first_chunk")), "chunks_sample": truncate_value(result.get("chunks_sample")), "error": result.get("error")}


def prefix_cache_test(name: str, payloads: tuple[dict[str, Any], dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    first = result.get("first", {})
    second = result.get("second", {})
    supported = bool(result.get("ok"))
    return {
        "name": name,
        "supported": supported,
        "status_code": result.get("status_code"),
        "request_body": {"first": payloads[0], "second": payloads[1]},
        "response_format": response_format(second.get("json")),
        "response_sample": {"first": truncate_value(first.get("json")), "second": truncate_value(second.get("json"))} if first.get("ok") or second.get("ok") else None,
        "error_sample": None if supported else truncate_value({"first": error_sample(first), "second": error_sample(second)}),
        "cached_tokens": result.get("cached_tokens"),
        "error": result.get("error"),
    }


def skipped_test(name: str, request_body: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"name": name, "supported": False, "skipped": True, "reason": reason, "status_code": None, "request_body": request_body, "response_sample": None, "error_sample": None, "error": None}


def response_format(sample: Any) -> dict[str, Any]:
    return {
        "top_level_keys": list(sample.keys()) if isinstance(sample, dict) else [],
        "has_id": safe_get(sample, "id") is not None,
        "has_model": safe_get(sample, "model") is not None,
        "has_choices": safe_get(sample, "choices") is not None,
        "has_message": safe_get(sample, "choices", 0, "message") is not None,
        "has_content": has_key(sample, "content"),
        "has_usage": safe_get(sample, "usage") is not None,
        "has_prompt_tokens_details": safe_get(sample, "usage", "prompt_tokens_details") is not None,
        "has_cached_tokens": safe_get(sample, "usage", "prompt_tokens_details", "cached_tokens") is not None,
        "has_output": safe_get(sample, "output") is not None,
        "has_output_text": safe_get(sample, "output_text") is not None,
        "has_tool_calls": has_tool_call(sample),
        "has_error": has_key(sample, "error"),
    }


def has_usage(sample: Any) -> bool:
    return safe_get(sample, "usage") is not None


def has_error_format(result: dict[str, Any]) -> bool:
    return not result.get("ok") and (result.get("json") is not None or bool(result.get("text")) or result.get("error") is not None)


def has_tool_call(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"tool_calls", "tool_call", "function_call"} and item:
                return True
            if lowered == "type" and str(item).lower() in {"tool_call", "function_call", "tool_use"}:
                return True
            if has_tool_call(item):
                return True
    if isinstance(value, list):
        return any(has_tool_call(item) for item in value)
    return False


def has_key(value: Any, key_name: str) -> bool:
    if isinstance(value, dict):
        return key_name in value or any(has_key(item, key_name) for item in value.values())
    if isinstance(value, list):
        return any(has_key(item, key_name) for item in value)
    return False


def classify_error(result: dict[str, Any]) -> dict[str, Any]:
    return {"type": "http_error" if result.get("status_code") else "request_error", "status_code": result.get("status_code"), "error": result.get("error")}


def error_sample(result: dict[str, Any]) -> dict[str, Any]:
    return {"status_code": result.get("status_code"), "json": result.get("json"), "text": result.get("text"), "error": result.get("error")}


def safe_get(value: Any, *path: str | int) -> Any:
    current = value
    for part in path:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and isinstance(part, int) and 0 <= part < len(current):
            current = current[part]
        else:
            return None
    return current


def truncate_value(value: Any, max_chars: int = 8000) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return value
    if isinstance(value, str):
        return value[:max_chars] + "...[truncated]"
    return {"__truncated__": True, "preview": text[:max_chars] + "...[truncated]"}


def _loads_or_none(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


def _loads_or_text(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return text


def log_capability(label: str, ok: bool, result: dict[str, Any]) -> None:
    state = "OK" if ok else "FAILED"
    status = result.get("status_code")
    suffix = f", status={status}" if status is not None else f", {result.get('error')}" if result.get("error") else ""
    print(f"[probe]   - {label}: {state}{suffix}")


def save_results(result_log: str, payload: dict[str, Any]) -> None:
    path = Path(result_log)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n>>> Results saved to {path}")


def get_region_from_host(host):
    region_map = {
        "ksai.scnet.cn": "昆山",
        "zzai.scnet.cn": "郑州",
        "zzai.scnet.ai": "纽约",
        "dzai.scnet.cn": "达州",
        "qdai.scnet.cn": "青岛",
        "szai.scnet.cn": "深圳",
        "sd5ai.scnet.cn": "魏桥",
        "whai.scnet.cn": "武汉",
    }
    for suffix, region in region_map.items():
        if host.endswith(suffix):
            return region
    return None


def probe_liveness(url_prefix):
    request = urllib.request.Request(f"{url_prefix}/v1/models", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=LIVENESS_TIMEOUT_SECONDS) as response:
            status = response.status
            text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return _liveness_skeleton(url_prefix, exc.code)
    except Exception as exc:
        details = _liveness_skeleton(url_prefix, "Connection failed")
        details["error"] = str(exc)
        return details

    details = _liveness_skeleton(url_prefix, status)
    if status != 200:
        return details

    model_data = _loads_or_none(text)
    if model_data is None:
        details["models_status"] = "Invalid JSON"
        return details

    models = model_data.get("data", [])
    details["models_ok"] = True
    details["models"] = models
    if models:
        details["first_model"] = models[0].get("id", "")
    return details


def _liveness_skeleton(url_prefix, status):
    return {
        "url_prefix": url_prefix,
        "models_status": status,
        "models_ok": False,
        "models": [],
        "first_model": "",
        "probe_result": None,
        "protocol_status": {},
    }


def probe_host_full(liveness):
    details = dict(liveness)
    details["probe_result"] = None
    details["protocol_status"] = {}
    if not details.get("first_model"):
        return details

    result = probe_service(
        base_url=details["url_prefix"],
        model=details["first_model"],
        protocols=PROTOCOLS,
        output_tokens=128,
        temperature=0.0,
        request_timeout_seconds=PROBE_TIMEOUT_SECONDS,
    )
    details["probe_result"] = result
    details["protocol_status"] = {
        name: {
            "supported": item.get("supported", False),
            "status_code": item.get("status_code"),
            "capabilities": item.get("capabilities", {}),
            "tests": item.get("tests", {}),
        }
        for name, item in result.get("protocols", {}).items()
    }
    return details


def collect_model_probes(clusters_data):
    probe_records = []
    all_models = {}

    for _, data in clusters_data.items():
        for record in data.get("records", []):
            if record["name"] == "maas-test":
                continue
            if not record["hosts"]:
                all_models[record["name"]] = {
                    "protocols": {},
                    "replicas": f"{record['replicas']}/{record['available']}",
                    "region": None,
                }
            else:
                probe_records.append(record)

    # 阶段1：并发对每个 (record, host) 做轻量探活（/v1/models）。
    liveness_tasks = [
        (idx, host, f"http://{host}:58000")
        for idx, record in enumerate(probe_records)
        for host in record["hosts"]
    ]
    liveness_map = {}
    with ThreadPoolExecutor(max_workers=MAX_PROBE_WORKERS) as executor:
        futures = {
            executor.submit(probe_liveness, url): (idx, host)
            for idx, host, url in liveness_tasks
        }
        for future in as_completed(futures):
            liveness_map[futures[future]] = future.result()

    # 阶段2：每个 record 选一个探活成功的主机做完整探测（同一 record 的多 host 通常是
    # 同一 service 的别名，只探主机即可，避免对每个 host 重复跑完整能力测试）。
    full_tasks = []
    for idx, record in enumerate(probe_records):
        live_hosts = sorted(
            (h for h in record["hosts"] if liveness_map.get((idx, h), {}).get("first_model")),
            key=lambda h: host_sort_key(h, record["name"]),
        )
        if live_hosts:
            full_tasks.append((idx, liveness_map[(idx, live_hosts[0])]))

    # 阶段3：并发完整探测。
    full_map = {}
    with ThreadPoolExecutor(max_workers=MAX_PROBE_WORKERS) as executor:
        futures = {
            executor.submit(probe_host_full, liveness): idx
            for idx, liveness in full_tasks
        }
        for future in as_completed(futures):
            full_map[futures[future]] = future.result()

    # 阶段4：组装结果。
    region_groups = {}
    for idx, record in enumerate(probe_records):
        primary_host = pick_primary_host(record["hosts"], record["name"])
        region = get_region_from_host(primary_host) if primary_host else None
        probe = full_map.get(idx)

        if probe and probe.get("probe_result"):
            all_models[record["name"]] = {
                "protocols": probe.get("protocol_status", {}),
                "replicas": f"{record['replicas']}/{record['available']}",
                "region": region,
                "probe": probe,
                "record": record,
            }
            if region:
                region_groups.setdefault(region, []).append(
                    (record["name"], all_models[record["name"]])
                )
        else:
            all_models[record["name"]] = {
                "protocols": {},
                "replicas": f"{record['replicas']}/{record['available']}",
                "region": region,
            }

    return all_models, region_groups


PROTOCOL_LABELS = {
    "chat_completions": "OpenAI Chat Completions",
    "responses": "OpenAI Responses",
    "anthropic_messages": "Anthropic Messages",
}
CAPABILITY_COLUMNS = [
    ("basic", "basic"),
    ("stream", "stream"),
    ("usage", "usage"),
    ("tool_calls", "tool_calls"),
    ("json_output", "JSON output"),
    ("structured_output", "structured output"),
    ("error_format", "error format"),
]


def yes_no(value):
    return "✅" if value else "❌"


def render_markdown(all_models, region_groups):
    md = ""
    md += "# 模型服务信息\n\n"
    md += "## 模型总览\n\n"
    md += "| 模型 | Chat | Responses | Anthropic | 副本数 |\n"
    md += "|------|------|-----------|-----------|--------|\n"

    for model_name in sorted(all_models.keys()):
        model_info = all_models[model_name]
        protocol_status = model_info.get("protocols", {})
        chat = "✅" if protocol_status.get("chat_completions", {}).get("supported") else "❌"
        responses = "✅" if protocol_status.get("responses", {}).get("supported") else "❌"
        anthropic = "✅" if protocol_status.get("anthropic_messages", {}).get("supported") else "❌"
        md += f"| {model_name} | {chat} | {responses} | {anthropic} | {model_info['replicas']} |\n"

    md += "\n"

    for region in sorted(region_groups.keys()):
        md += f"## {region}\n\n"
        for model_name, model_info in region_groups[region]:
            md += f"### {model_name}\n"
            probe = model_info["probe"]
            record = model_info["record"]
            protocol_status = probe.get("protocol_status", {})

            first_model = probe.get("first_model", "")
            first_max_len = "N/A"
            if probe.get("models"):
                first_max_len = probe["models"][0].get("max_model_len", "N/A")

            md += "**模型信息**\n\n"
            md += f"- 模型名称: {model_name}\n"
            md += f"- base_url: {probe['url_prefix']}\n"
            md += f"- model_id: {first_model}\n"
            md += f"- 模型最大上下文长度: {first_max_len}\n"
            md += f"- 副本数: {record['replicas']}/{record['available']}\n\n"

            header = ["协议", "支持", "状态码"] + [label for _, label in CAPABILITY_COLUMNS]
            md += "**协议支持总览**\n\n"
            md += "| " + " | ".join(header) + " |\n"
            md += "|" + "|".join("---" for _ in header) + "|\n"
            for protocol in PROTOCOLS:
                item = protocol_status.get(protocol, {})
                caps = item.get("capabilities", {})
                status_code = item.get("status_code")
                cells = [
                    PROTOCOL_LABELS.get(protocol, protocol),
                    yes_no(item.get("supported")),
                    str(status_code) if status_code is not None else "-",
                ]
                cells += [yes_no(caps.get(key)) for key, _ in CAPABILITY_COLUMNS]
                md += "| " + " | ".join(cells) + " |\n"
            md += "\n"

            if first_model:
                md += "请求示例:\n"
                md += "```bash\n"
                md += f"curl -X POST '{probe['url_prefix']}/v1/chat/completions' \\\n"
                md += "  -H 'Content-Type: application/json' \\\n"
                md += "  -d '{\n"
                md += f'    "model": "{first_model}",\n'
                md += '    "messages": [{"role": "user", "content": "你好"}],\n'
                md += '    "temperature": 0.7,\n'
                md += '    "stream": false\n'
                md += "  }'\n"
                md += "```\n"

                if protocol_status.get("responses", {}).get("supported"):
                    md += "OpenAI Responses 示例:\n"
                    md += "```bash\n"
                    md += f"curl -X POST '{probe['url_prefix']}/v1/responses' \\\n"
                    md += "  -H 'Content-Type: application/json' \\\n"
                    md += "  -d '{\n"
                    md += f'    "model": "{first_model}",\n'
                    md += '    "input": "你好，请用一句话介绍你自己",\n'
                    md += '    "max_output_tokens": 128\n'
                    md += "  }'\n"
                    md += "```\n"
                    if protocol_status.get("responses", {}).get("tests", {}).get("prefix_cache_usage", {}).get("supported"):
                        md += "OpenAI Responses 前缀缓存示例:\n"
                        md += "```bash\n"
                        md += f"curl -X POST '{probe['url_prefix']}/v1/responses' \\\n"
                        md += "  -H 'Content-Type: application/json' \\\n"
                        md += "  -d '{\n"
                        md += f'    "model": "{first_model}",\n'
                        md += '    "input": "This is a shared long prefix for testing prefix-cache usage.\\nQuestion one: Reply with exactly: first round.",\n'
                        md += '    "max_output_tokens": 128\n'
                        md += "  }'\n"
                        md += "```\n"

            md += "\n"

    return md


def main():
    clusters_data = {}
    for cluster in CLUSTERS:
        clusters_data[cluster["name"]] = collect_cluster_data(cluster)

    all_models, region_groups = collect_model_probes(clusters_data)
    markdown = render_markdown(all_models, region_groups)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file_obj:
        file_obj.write(markdown)

    print(f"报告已生成: {OUTPUT_FILE}")

    if FEISHU_DOC:
        print(f"\n正在更新飞书文档...")
        update_cmd = [
            "lark-cli", "docs", "+update", "--api-version", "v2",
            "--doc", FEISHU_DOC,
            "--command", "overwrite",
            "--doc-format", "markdown",
            "--content", f"@{OUTPUT_FILE}",
        ]
        result = subprocess.run(update_cmd, capture_output=True, text=True, cwd=os.path.dirname(OUTPUT_FILE))
        if result.returncode == 0:
            print("飞书文档更新成功")
        else:
            print(f"飞书文档更新失败: {result.stderr}")

    print("\n" + markdown)


if __name__ == "__main__":
    main()
