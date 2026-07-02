#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import os


REMOTE_CONF_FILE = "/etc/ex-lb/conf/ex-lb.conf"
PLACEHOLDER = "$NODE_IP"
CONF_DIR = os.path.expanduser("~/sugon/ske-chart/ex-lb")
CLUSTERS_JSON = os.path.expanduser("~/agent/ex-lb/clusters.json")


def load_clusters():
    with open(CLUSTERS_JSON) as f:
        return json.load(f)


def run(cmd, timeout=300, check=False):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if check and r.returncode != 0:
            print(f"  Error: {' '.join(cmd)}")
            print(f"  stderr: {r.stderr}")
            return False
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  Error: timeout: {' '.join(cmd)}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def backup(ctx, node_ip):
    print(f"  Backup on {node_ip}")
    return run([
        "kubectl", "node-shell", "--context", ctx, node_ip, "--",
        "cp", "-f", REMOTE_CONF_FILE, f"{REMOTE_CONF_FILE}.bak"
    ], check=True)


def upload(ctx, node_ip, content):
    print(f"  Upload to {node_ip}")
    filled = content.replace(PLACEHOLDER, node_ip)
    r = subprocess.run(
        ["kubectl", "node-shell", "--context", ctx, node_ip, "--",
         "sh", "-c", f"cat > {REMOTE_CONF_FILE}"],
        input=filled.encode(), capture_output=True, timeout=300
    )
    if r.returncode != 0:
        print(f"  Error: {r.stderr.decode()}")
        return False
    return True


def verify(ctx, node_ip):
    print(f"  Verify on {node_ip}")
    return run([
        "kubectl", "node-shell", "--context", ctx, node_ip, "--",
        "/etc/ex-lb/sbin/ex-lb", "-c", REMOTE_CONF_FILE, "-t"
    ], check=False)


def reload(ctx, node_ip):
    print(f"  Reload on {node_ip}")
    return run([
        "kubectl", "node-shell", "--context", ctx, node_ip, "--",
        "systemctl", "reload", "ex-lb"
    ])


def rollback(ctx, node_ip, content):
    print(f"  Rollback on {node_ip}")
    run([
        "kubectl", "node-shell", "--context", ctx, node_ip, "--",
        "cp", "-f", f"{REMOTE_CONF_FILE}.bak", REMOTE_CONF_FILE
    ])


def process_node(ctx, node_ip, content, no_reload):
    print(f"\n=== {ctx} / {node_ip} ===")
    if not backup(ctx, node_ip):
        return False
    if not upload(ctx, node_ip, content):
        return False
    if not verify(ctx, node_ip):
        print(f"  Verification failed, rollback...")
        rollback(ctx, node_ip, content)
        return False
    if no_reload:
        print(f"  Upload + verify OK, reload skipped (--no-reload)")
        return True
    if not reload(ctx, node_ip):
        print(f"  Reload failed")
        return False
    print(f"  OK")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Upload ex-lb config to all ex-lb nodes of a cluster",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Upload to all ex-lb nodes of dz:
    python ex-lb-conf-upload.py -c dz

  Upload to all ex-lb nodes of qd, skip reload:
    python ex-lb-conf-upload.py -c qd --no-reload

  Upload to multiple clusters:
    python ex-lb-conf-upload.py -c qd,wh,sz
        """,
    )
    parser.add_argument("-c", "--contexts", required=True,
                        help="Comma-separated contexts (e.g. dz,qd,wh)")
    parser.add_argument("--no-reload", action="store_true",
                        help="Skip reload (verify only)")
    parser.add_argument("--conf-dir", default=CONF_DIR,
                        help=f"Config dir (default: {CONF_DIR})")
    args = parser.parse_args()

    targets = [c.strip() for c in args.contexts.split(",")]
    all_ok = True

    clusters = load_clusters()

    for ctx in targets:
        if ctx not in clusters or not clusters[ctx].get("ex_lb_nodes"):
            print(f"[!] {ctx}: no ex-lb nodes configured, skipping")
            continue
        conf_path = os.path.join(args.conf_dir, f"ex-lb-{ctx}.conf")
        if not os.path.exists(conf_path):
            print(f"[!] {ctx}: config not found: {conf_path}, skipping")
            all_ok = False
            continue
        with open(conf_path) as f:
            content = f.read()
        nodes = clusters[ctx]["ex_lb_nodes"]
        print(f"\n{'='*40} {ctx.upper()} ({len(nodes)} nodes) {'='*40}")
        for node_ip in nodes:
            if not process_node(ctx, node_ip, content, args.no_reload):
                all_ok = False

    print(f"\n{'='*40}")
    print(f"{'OK' if all_ok else 'FAILED'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
