#!/usr/bin/env python3
"""
Render manifests for the default KubeSphere user bootstrap flow.

Default flow:
- username = workspace = namespace
- global role = platform-regular
- cluster role = cluster-viewer
- workspace role = <username>-admin
- namespace role = admin
- granted clusters = requested clusters
- namespace is marked as kubesphere-managed

The script only renders manifests. It never deletes resources.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Iterable


def build_user(username: str, email: str, password: str, clusters: list[str]) -> dict:
    return {
        "apiVersion": "iam.kubesphere.io/v1beta1",
        "kind": "User",
        "metadata": {
            "name": username,
            "annotations": {
                "iam.kubesphere.io/globalrole": "platform-regular",
                "iam.kubesphere.io/granted-clusters": ",".join(clusters),
                "kubesphere.io/creator": "admin",
            },
        },
        "spec": {
            "email": email,
            "password": password,
        },
    }


def build_global_role_binding(username: str) -> dict:
    return {
        "apiVersion": "iam.kubesphere.io/v1beta1",
        "kind": "GlobalRoleBinding",
        "metadata": {
            "name": f"{username}-platform-regular",
            "labels": {
                "iam.kubesphere.io/role-ref": "platform-regular",
                "iam.kubesphere.io/user-ref": username,
            },
        },
        "roleRef": {
            "apiGroup": "iam.kubesphere.io",
            "kind": "GlobalRole",
            "name": "platform-regular",
        },
        "subjects": [
            {
                "apiGroup": "iam.kubesphere.io",
                "kind": "User",
                "name": username,
            }
        ],
    }


def build_workspace_template(username: str, clusters: list[str]) -> dict:
    return {
        "apiVersion": "tenant.kubesphere.io/v1beta1",
        "kind": "WorkspaceTemplate",
        "metadata": {
            "name": username,
            "annotations": {
                "kubesphere.io/creator": "admin",
            },
        },
        "spec": {
            "placement": {
                "clusters": [{"name": cluster} for cluster in clusters],
            },
            "template": {
                "metadata": {
                    "annotations": {
                        "kubesphere.io/creator": "admin",
                    }
                },
                "spec": {
                    "manager": username,
                },
            },
        },
    }


def build_cluster_role_binding(username: str) -> dict:
    return {
        "apiVersion": "iam.kubesphere.io/v1beta1",
        "kind": "ClusterRoleBinding",
        "metadata": {
            "name": f"{username}-cluster-viewer",
            "labels": {
                "iam.kubesphere.io/role-ref": "cluster-viewer",
                "iam.kubesphere.io/user-ref": username,
            },
        },
        "roleRef": {
            "apiGroup": "iam.kubesphere.io",
            "kind": "ClusterRole",
            "name": "cluster-viewer",
        },
        "subjects": [
            {
                "apiGroup": "iam.kubesphere.io",
                "kind": "User",
                "name": username,
            }
        ],
    }


def build_workspace_role_binding(username: str) -> dict:
    return {
        "apiVersion": "iam.kubesphere.io/v1beta1",
        "kind": "WorkspaceRoleBinding",
        "metadata": {
            "name": f"{username}-admin",
            "labels": {
                "iam.kubesphere.io/role-ref": f"{username}-admin",
                "iam.kubesphere.io/user-ref": username,
                "kubesphere.io/workspace": username,
            },
        },
        "roleRef": {
            "apiGroup": "iam.kubesphere.io",
            "kind": "WorkspaceRole",
            "name": f"{username}-admin",
        },
        "subjects": [
            {
                "apiGroup": "iam.kubesphere.io",
                "kind": "User",
                "name": username,
            }
        ],
    }


def build_namespace(username: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": username,
            "labels": {
                "kubernetes.io/metadata.name": username,
                "kubesphere.io/managed": "true",
                "kubesphere.io/workspace": username,
            },
            "annotations": {
                "kubesphere.io/creator": "admin",
            },
        },
    }


def build_namespace_role_binding(username: str) -> dict:
    return {
        "apiVersion": "iam.kubesphere.io/v1beta1",
        "kind": "RoleBinding",
        "metadata": {
            "name": f"{username}-admin",
            "namespace": username,
            "labels": {
                "iam.kubesphere.io/role-ref": "admin",
                "iam.kubesphere.io/user-ref": username,
            },
        },
        "roleRef": {
            "apiGroup": "iam.kubesphere.io",
            "kind": "Role",
            "name": "admin",
        },
        "subjects": [
            {
                "apiGroup": "iam.kubesphere.io",
                "kind": "User",
                "name": username,
            }
        ],
    }


def render_documents(documents: Iterable[dict], stream) -> None:
    first = True
    for document in documents:
        if not first:
            stream.write("---\n")
        json.dump(document, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
        first = False


def kubectl_get_json(context: str, resource_args: list[str], name: str) -> dict | None:
    cmd = ["kubectl", "--context", context, "get", *resource_args, name, "-o", "json"]
    completed = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return json.loads(completed.stdout)


def resource_ref(document: dict) -> tuple[str, str]:
    api_version = document["apiVersion"]
    kind = document["kind"]

    if api_version == "v1" and kind == "Namespace":
        return ("namespaces", document["metadata"]["name"])
    if api_version == "iam.kubesphere.io/v1beta1" and kind == "User":
        return ("users.iam.kubesphere.io", document["metadata"]["name"])
    if api_version == "iam.kubesphere.io/v1beta1" and kind == "GlobalRoleBinding":
        return ("globalrolebindings.iam.kubesphere.io", document["metadata"]["name"])
    if api_version == "iam.kubesphere.io/v1beta1" and kind == "ClusterRoleBinding":
        return ("clusterrolebindings.iam.kubesphere.io", document["metadata"]["name"])
    if api_version == "tenant.kubesphere.io/v1beta1" and kind == "WorkspaceTemplate":
        return ("workspacetemplates.tenant.kubesphere.io", document["metadata"]["name"])
    if api_version == "iam.kubesphere.io/v1beta1" and kind == "WorkspaceRoleBinding":
        return ("workspacerolebindings.iam.kubesphere.io", document["metadata"]["name"])
    if api_version == "iam.kubesphere.io/v1beta1" and kind == "RoleBinding":
        return ("rolebindings.iam.kubesphere.io -n " + document["metadata"]["namespace"], document["metadata"]["name"])
    raise ValueError(f"Unsupported resource: {api_version} {kind}")


def resource_exists(context: str, document: dict) -> bool:
    resource, name = resource_ref(document)
    return kubectl_get_json(context, resource.split(), name) is not None


def filter_existing(context: str, documents: list[dict], verbose: bool) -> list[dict]:
    pending: list[dict] = []
    for document in documents:
        if resource_exists(context, document):
            if verbose:
                namespace = document["metadata"].get("namespace")
                scope = f" namespace={namespace}" if namespace else ""
                print(
                    f"skip existing: {document['kind']} name={document['metadata']['name']}{scope}",
                    file=sys.stderr,
                )
            continue
        pending.append(document)
    return pending


def parse_member_context_mapping(items: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in items:
        cluster, separator, context = item.partition("=")
        if not separator or not cluster or not context:
            raise SystemExit(
                f"invalid --member-context value {item!r}; expected <kubesphere-cluster-name>=<kubectl-context>"
            )
        mapping[cluster] = context
    return mapping


def namespace_is_workspace_managed(namespace: dict, username: str) -> bool:
    owner_references = namespace.get("metadata", {}).get("ownerReferences") or []
    return any(
        ref.get("kind") == "Workspace" and ref.get("name") == username
        for ref in owner_references
    )


def find_unmanaged_namespace_conflicts(
    username: str,
    clusters: list[str],
    member_contexts: dict[str, str],
) -> list[str]:
    conflicts: list[str] = []
    for cluster in clusters:
        context = member_contexts.get(cluster)
        if not context:
            continue
        namespace = kubectl_get_json(context, ["namespaces"], username)
        if namespace is None:
            continue
        if namespace_is_workspace_managed(namespace, username):
            continue

        metadata = namespace.get("metadata", {})
        labels = metadata.get("labels") or {}
        owner_references = metadata.get("ownerReferences") or []
        owner_summary = (
            ",".join(
                f"{ref.get('kind', '?')}/{ref.get('name', '?')}"
                for ref in owner_references
            )
            if owner_references
            else "none"
        )
        conflicts.append(
            f"- cluster={cluster} context={context} namespace={username} "
            f"workspace_label={labels.get('kubesphere.io/workspace', '')!r} "
            f"managed_label={labels.get('kubesphere.io/managed', '')!r} "
            f"ownerReferences={owner_summary}"
        )
    return conflicts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render manifests for the default KubeSphere user bootstrap flow."
    )
    parser.add_argument("--username", required=True, help="Username, workspace, and namespace name")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", required=True, help="Initial plaintext password")
    parser.add_argument(
        "--cluster",
        action="append",
        dest="clusters",
        default=[],
        help="Target KubeSphere cluster name. Repeatable.",
    )
    parser.add_argument("--output", help="Write manifests to file instead of stdout")
    parser.add_argument("--context", help="kubectl context used with --skip-existing")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Probe the cluster and skip resources that already exist",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print skipped resources to stderr when --skip-existing is used",
    )
    parser.add_argument(
        "--member-context",
        action="append",
        default=[],
        help=(
            "Map a KubeSphere member cluster to a local kubectl context for namespace preflight. "
            "Format: <kubesphere-cluster-name>=<kubectl-context>. Repeatable."
        ),
    )
    parser.add_argument(
        "--allow-unmanaged-preexisting-namespace",
        action="store_true",
        help=(
            "Allow rendering manifests even when a target member cluster already has the same namespace "
            "without Workspace ownerReferences. Use only when you have a separate adoption or rebuild plan."
        ),
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not args.clusters:
        raise SystemExit("at least one --cluster is required")
    if args.skip_existing and not args.context:
        raise SystemExit("--context is required when --skip-existing is set")
    args.member_context_map = parse_member_context_mapping(args.member_context)


def validate_member_namespaces(args: argparse.Namespace) -> None:
    conflicts = find_unmanaged_namespace_conflicts(
        args.username,
        args.clusters,
        args.member_context_map,
    )
    if conflicts and not args.allow_unmanaged_preexisting_namespace:
        details = "\n".join(conflicts)
        raise SystemExit(
            "refusing to render bootstrap manifests because an unmanaged preexisting namespace was found.\n"
            "Applying the default Namespace manifest on top of an existing namespace only adds labels; "
            "it does not make KubeSphere adopt that namespace as a Workspace-managed project.\n"
            "This can leave the user unable to see the member cluster in the console.\n"
            "Resolve by deleting/rebuilding the namespace through Workspace placement, or rerun with "
            "--allow-unmanaged-preexisting-namespace only if you have a separate reconciliation plan.\n"
            f"{details}"
        )


def main() -> int:
    args = parse_args()
    validate_args(args)
    validate_member_namespaces(args)

    documents: list[dict] = [
        build_user(args.username, args.email, args.password, args.clusters),
        build_global_role_binding(args.username),
        build_cluster_role_binding(args.username),
        build_workspace_template(args.username, args.clusters),
        build_workspace_role_binding(args.username),
        build_namespace(args.username),
        build_namespace_role_binding(args.username),
    ]

    if args.skip_existing:
        documents = filter_existing(args.context, documents, args.verbose)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            render_documents(documents, handle)
    else:
        render_documents(documents, sys.stdout)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
