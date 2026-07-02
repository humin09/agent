#!/usr/bin/env python3
"""ex-lb 工作验证脚本：DNS 解析 + HTTP 探测"""
import argparse
import json
import subprocess
import sys
import re
import time
import os


NETSHOOT_IMAGE = "image.ac.com:5000/k8s/netshoot"
CLUSTERS_JSON = os.path.expanduser("~/agent/ex-lb/clusters.json")


def load_clusters():
    with open(CLUSTERS_JSON) as f:
        data = json.load(f)
    clusters = {}
    for ctx, cfg in data.items():
        if not cfg.get("ex_lb_nodes"):
            continue
        if not cfg.get("vm_local") or not cfg.get("image_ac") or not cfg.get("wildcard_ip"):
            continue
        clusters[ctx] = cfg
    return clusters


CLUSTERS = load_clusters()


def run(cmd, timeout=30, check=False):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if check and r.returncode != 0:
            return None, r.stderr.strip()
        return r.stdout + r.stderr, None
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception as e:
        return None, str(e)


def create_test_pod(ctx, node_ip, pod_name):
    safe = re.sub(r'\.', '-', node_ip)
    name = f"exlbtest-{safe}"
    run(["kubectl", "--context", ctx, "delete", "pod", name,
         "--force", "--grace-period=0"], timeout=15)
    time.sleep(2)
    overrides = {
        "spec": {
            "hostNetwork": True,
            "nodeName": node_ip,
            "tolerations": [{"operator": "Exists"}]
        }
    }
    import json
    cmd = [
        "kubectl", "--context", ctx, "run", name,
        "--image", NETSHOOT_IMAGE,
        "--overrides", json.dumps(overrides),
        "--", "sleep", "600"
    ]
    out, err = run(cmd, timeout=30)
    if err and "error" in str(err).lower():
        print(f"  [!] Failed to create pod: {err}")
        return None
    time.sleep(10)
    return name


def delete_test_pod(ctx, pod_name):
    if pod_name:
        run(["kubectl", "--context", ctx, "delete", "pod", pod_name,
             "--force", "--grace-period=0"], timeout=15)


def nslookup(ctx, pod, hostname, dns_server):
    out, err = run([
        "kubectl", "--context", ctx, "exec", pod, "--",
        "nslookup", hostname, dns_server
    ], timeout=15)
    if err:
        return None, err
    matches = re.findall(r'Address:\s*([\d\.]+)', out)
    if len(matches) >= 2:
        return matches[1], None
    if matches:
        return matches[0], None
    if "NXDOMAIN" in (out or "") or "can't find" in (out or ""):
        return None, "NXDOMAIN"
    return None, (out or "").strip()[-100:]


def test_cluster(ctx, cfg):
    node = cfg["ex_lb_nodes"][0]
    results = []

    print(f"\n{'='*60}")
    print(f"  {ctx.upper()} | VIP={cfg['vip']} | domain={cfg['domain']}")
    print(f"{'='*60}")

    pod = create_test_pod(ctx, node, node)
    if not pod:
        return []

    checks = [
        ("vm.local", node, cfg["vm_local"]),
        ("image.ac.com", node, cfg["image_ac"]),
        (f"aa.{cfg['domain']}", node, cfg["wildcard_ip"]),
    ]

    for host, dns, expected in checks:
        ip, err = nslookup(ctx, pod, host, dns)
        ok = ip == expected
        mark = "\033[32m✓\033[0m" if ok else "\033[31m✗\033[0m"
        detail = ip if ip else err or "no result"
        print(f"  {mark} DNS {host:<25} via {dns:<18} → {detail:<18} (expect {expected})")
        results.append(("DNS", host, ok))

    delete_test_pod(ctx, pod)

    ingress_url = f"https://ingress.{cfg['domain']}:{cfg['port']}/"
    out, err = run(
        ["curl", "-sk", "--connect-timeout", "5",
         "-o", "/dev/null", "-w", "%{http_code}", ingress_url],
        timeout=10
    )
    code = (out or "").strip()
    ok = code == "200"
    mark = "\033[32m✓\033[0m" if ok else "\033[31m✗\033[0m"
    print(f"  {mark} HTTP {ingress_url:<45} → HTTP {code}")
    results.append(("HTTP", ingress_url, ok))

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Test ex-lb DNS + HTTP per cluster",
        epilog="Examples:\n"
               "  python ex-lb-conf-test.py -c dz\n"
               "  python ex-lb-conf-test.py -c qd,wh,sz\n"
               "  python ex-lb-conf-test.py --all\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-c", "--contexts", help="Comma-separated cluster contexts (e.g. dz,qd,wh)")
    parser.add_argument("--all", action="store_true", help="Test all clusters")
    args = parser.parse_args()

    if args.all:
        targets = list(CLUSTERS.keys())
    elif args.contexts:
        targets = [c.strip() for c in args.contexts.split(",")]
    else:
        parser.error("Must specify -c or --all")

    all_results = []
    for ctx in targets:
        if ctx not in CLUSTERS:
            print(f"  [!] Unknown context: {ctx}, skipping")
            continue
        all_results.extend(test_cluster(ctx, CLUSTERS[ctx]))

    total = len(all_results)
    passed = sum(1 for _, _, ok in all_results if ok)
    failed = total - passed

    print(f"\n{'='*60}")
    color = "\033[32m" if failed == 0 else "\033[31m"
    print(f"  {color}Total: {total} | Passed: {passed} | Failed: {failed}\033[0m")
    print(f"{'='*60}\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
