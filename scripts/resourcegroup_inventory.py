#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys

CONTEXTS = ["ks", "dz", "qd", "wh", "sz", "zz", "wq", "ny"]


def kubectl(context, args):
    cmd = ["kubectl", f"--context={context}", "-o", "json"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return None, r.stderr.strip()
    try:
        return json.loads(r.stdout), None
    except json.JSONDecodeError:
        return None, r.stdout


def get_resourcegroup(context, group_id):
    data, err = kubectl(context, ["-n", "kube-system", "get", "resourcegroup"])
    if err:
        return None, err
    items = data.get("items", [])
    for rg in items:
        gid = (rg.get("spec", {}).get("labels", {}).get("groupId", "")
               or rg.get("status", {}).get("groupId", "")
               or rg.get("spec", {}).get("groupId", ""))
        if str(gid) == str(group_id):
            return rg, None
    return None, "not found"


def get_node_devices(context, node, card_type):
    if card_type == "dcu":
        res_key = "hygon.com/dcu"
    else:
        res_key = "nvidia.com/gpu"
    data, err = kubectl(context, ["get", "node", node])
    if err:
        return 0, 0, "unknown"
    alloc = data.get("status", {}).get("allocatable", {})
    cap = data.get("status", {}).get("capacity", {})
    alloc_n = int(alloc.get(res_key, 0))
    cap_n = int(cap.get(res_key, alloc_n))
    arch = data.get("status", {}).get("nodeInfo", {}).get("architecture", "unknown")
    return alloc_n, cap_n, arch


def main():
    parser = argparse.ArgumentParser(description="ResourceGroup DCU/GPU inventory")
    parser.add_argument("group_id", help="ResourceGroup GROUPID")
    parser.add_argument("--card-type", default="dcu", choices=["dcu", "gpu"], help="Card type (default: dcu)")
    parser.add_argument("--context", "-c", action="append", help="Limit to specific contexts")
    args = parser.parse_args()

    contexts = args.context or CONTEXTS
    group_id = args.group_id
    card_type = args.card_type

    print(f"Scanning resource groups with groupId={group_id}, card-type={card_type}\n")

    total_devices = 0
    total_nodes = 0
    found_any = False

    for ctx in contexts:
        rg, err = get_resourcegroup(ctx, group_id)
        if err:
            if "not found" not in str(err):
                print(f"[{ctx}] Error: {err}")
            continue

        found_any = True
        spec = rg.get("spec", {})
        labels = spec.get("labels", {})
        name = rg["metadata"]["name"]
        node_names = spec.get("nodeNames", [])
        ns = spec.get("namespaces", [])
        card = labels.get("card", "unknown")
        svc_type = labels.get("serviceType", "unknown")

        print(f"[{ctx}] ResourceGroup: {name} (groupId={group_id})")
        print(f"       card: {card}, serviceType: {svc_type}")
        print(f"       namespaces: {ns if ns else '(shared)'}")
        print(f"       nodeNames: {len(node_names)} nodes")

        if node_names:
            cluster_devices = 0
            for node in node_names:
                alloc_n, cap_n, arch = get_node_devices(ctx, node, card_type)
                cluster_devices += alloc_n
                print(f"         - {node}: allocatable={alloc_n} capacity={cap_n} arch={arch}")
            print(f"       cluster total: {cluster_devices} {card_type.upper()}")
            total_devices += cluster_devices
            total_nodes += len(node_names)
        print()

    if not found_any:
        print(f"No resource group with groupId={group_id} found in contexts: {contexts}")
        sys.exit(1)

    print("=" * 60)
    print(f"Grand total: {total_nodes} nodes, {total_devices} {card_type.upper()} cards")


if __name__ == "__main__":
    main()
