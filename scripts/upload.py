#!/usr/bin/env python3
import argparse
import os
import posixpath
import shlex
import subprocess
import sys
import re


PROTECTED_REMOTE_DIRS = ("/public", "/work", "/data")
MINIO_BUCKET = "tmp"
LOCAL_MINIO_ALIAS = "k8s-scp-local"
AUTO_MINIO_THRESHOLD_BYTES = 100 * 1024 * 1024
MINIO_ENDPOINTS = {
    "ks": "http://minio.ksai.scnet.cn:9000",
    "qd": "http://minio.qdai.scnet.cn:9000",
    "dz": "http://minio.dzai.scnet.cn:9000",
    "zz": "http://minio.zzai2.scnet.cn:9000",
    "wh": "http://minio.whai.scnet.cn:9000",
    "sz": "http://minio.szai.scnet.cn:9000",
}
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "SugonMinio2024_pro"


def parse_remote_path(path):
    """解析远程路径，返回 (node_ip, remote_path) 或 (None, None)"""
    match = re.match(r"^([^:]+)(?::(.*))?$", path)
    if match:
        return match.group(1), match.group(2)
    return None, None


def is_remote_path(path, allow_node_only=False):
    """判断是否为远程路径"""
    node_ip, remote_path = parse_remote_path(path)
    if node_ip is None:
        return False
    if ":" in path:
        return True
    if not allow_node_only:
        return False
    return re.match(r"^[A-Za-z0-9._-]+$", path) is not None


def quote_remote_path(path):
    """对远端 shell 路径做安全转义"""
    return shlex.quote(path)


def resolve_remote_target_path(local_path, remote_path):
    """解析上传目标路径，支持 node_ip / node_ip: / node_ip:. / 目录路径"""
    if remote_path in {None, "", "."}:
        return posixpath.join("/tmp", os.path.basename(local_path))
    if remote_path.endswith("/"):
        return posixpath.join(remote_path, os.path.basename(local_path))
    return remote_path


def resolve_local_target_path(remote_path, local_path):
    """解析下载目标路径，支持本地目录和 ."""
    remote_name = posixpath.basename(remote_path.rstrip("/")) or "downloaded_file"
    local_is_dir = local_path in {"", "."} or local_path.endswith(os.sep)

    if not local_is_dir and os.path.exists(local_path):
        local_is_dir = os.path.isdir(local_path)

    if local_is_dir:
        target_dir = local_path or "."
        os.makedirs(target_dir, exist_ok=True)
        return os.path.join(target_dir, remote_name)

    parent_dir = os.path.dirname(local_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    return local_path


def format_command_for_log(cmd):
    return " ".join(shlex.quote(part) for part in cmd)


def is_protected_remote_path(path):
    normalized = posixpath.normpath(path)
    return any(
        normalized == protected or normalized.startswith(f"{protected}/")
        for protected in PROTECTED_REMOTE_DIRS
    )


def run_command(cmd, timeout=None, capture_output=True):
    return subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        timeout=timeout,
    )


def ensure_local_mc_alias(context, timeout):
    endpoint = MINIO_ENDPOINTS.get(context)
    if not endpoint:
        raise ValueError(
            f"Context '{context}' does not have a configured MinIO endpoint"
        )

    cmd = [
        "mc",
        "alias",
        "set",
        LOCAL_MINIO_ALIAS,
        endpoint,
        MINIO_ACCESS_KEY,
        MINIO_SECRET_KEY,
    ]
    result = run_command(cmd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def ensure_bucket_exists(alias, timeout):
    cmd = ["mc", "mb", "--ignore-existing", f"{alias}/{MINIO_BUCKET}"]
    result = run_command(cmd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def upload_file_to_minio(context, local_path, object_name=None, timeout=300):
    try:
        if not os.path.exists(local_path):
            print(f"Error: Local file '{local_path}' does not exist")
            return False

        if os.path.isdir(local_path):
            print(f"Error: '{local_path}' is a directory, only files are supported")
            return False

        if object_name is None:
            object_name = os.path.basename(local_path)

        file_size = os.path.getsize(local_path)
        print(f"Uploading {local_path} ({file_size} bytes) to MinIO tmp bucket")

        ensure_local_mc_alias(context, timeout)
        ensure_bucket_exists(LOCAL_MINIO_ALIAS, timeout)

        cmd = ["mc", "cp", local_path, f"{LOCAL_MINIO_ALIAS}/{MINIO_BUCKET}/{object_name}"]
        print(f"Executing: {format_command_for_log(cmd)}")
        result = subprocess.run(cmd, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError("mc cp to MinIO failed")

        print(
            f"File uploaded successfully to: "
            f"{LOCAL_MINIO_ALIAS}/{MINIO_BUCKET}/{object_name}"
        )
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def copy_file_to_node(context, node_ip, local_path, remote_path, timeout=300):
    """
    Copy file from local to Kubernetes node using kubectl node-shell
    """
    try:
        if not os.path.exists(local_path):
            print(f"Error: Local file '{local_path}' does not exist")
            return False

        if os.path.isdir(local_path):
            print(
                f"Error: '{local_path}' is a directory. Use directory copy tool for directories."
            )
            return False

        remote_path = resolve_remote_target_path(local_path, remote_path)
        if is_protected_remote_path(remote_path):
            print(
                "Error: Upload to protected remote paths is not allowed: "
                f"{', '.join(PROTECTED_REMOTE_DIRS)}"
            )
            return False
        remote_dir = posixpath.dirname(remote_path) or "."
        quoted_remote_dir = quote_remote_path(remote_dir)
        quoted_remote_path = quote_remote_path(remote_path)

        print(f"Uploading {local_path} to {node_ip}:{remote_path}")

        cmd = [
            "kubectl",
            "node-shell",
            "--context",
            context,
            node_ip,
            "--",
            "sh",
            "-c",
            f"mkdir -p -- {quoted_remote_dir} && cat > {quoted_remote_path}",
        ]

        print(f"Executing: {format_command_for_log(cmd)}")

        with open(local_path, "rb") as source_file:
            result = subprocess.run(
                cmd, stdin=source_file, capture_output=True, timeout=timeout
            )

        if result.returncode != 0:
            print(f"Error: {result.stderr.decode('utf-8', errors='ignore')}")
            return False

        print(f"File uploaded successfully to: {node_ip}:{remote_path}")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def copy_file_from_node(context, node_ip, remote_path, local_path, timeout=300):
    """
    Copy file from Kubernetes node to local using kubectl node-shell
    """
    try:
        local_path = resolve_local_target_path(remote_path, local_path)
        quoted_remote_path = quote_remote_path(remote_path)

        print(f"Downloading {node_ip}:{remote_path} to {local_path}")

        cmd = [
            "kubectl",
            "node-shell",
            "--context",
            context,
            node_ip,
            "--",
            "sh",
            "-c",
            f"cat -- {quoted_remote_path}",
        ]

        print(f"Executing: {format_command_for_log(cmd)}")

        with open(local_path, "wb") as target_file:
            result = subprocess.run(
                cmd,
                stdout=target_file,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )

        if result.returncode != 0:
            try:
                os.remove(local_path)
            except OSError:
                pass
            print(f"Error: {result.stderr.decode('utf-8', errors='ignore')}")
            return False

        print(f"File downloaded successfully to: {local_path}")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def choose_minio_object_name(local_path, remote_path):
    if remote_path:
        remote_name = posixpath.basename(remote_path.rstrip("/"))
        if remote_name and remote_name not in {".", "/"}:
            return remote_name
    return os.path.basename(local_path)


def main():
    parser = argparse.ArgumentParser(
        description="Kubernetes file transfer - Copy files to/from Kubernetes nodes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Upload file to node:
    python upload-k8s.py -c qd local_file.txt 10.1.4.9:/remote/path/file.txt

  Upload file to MinIO tmp bucket explicitly:
    python upload-k8s.py -c qd --minio-only /tmp/large-file.tar.gz

  Upload file to /tmp on node (default when path omitted):
    python upload-k8s.py -c qd local_file.txt 10.1.4.9

  Download file from node:
    python upload-k8s.py -c qd 10.1.4.9:/remote/path/file.txt local_file.txt

  Upload to current directory on node:
    python upload-k8s.py -c qd local_file.txt 10.1.4.9:.

  Download from current directory on node:
    python upload-k8s.py -c qd 10.1.4.9:remote_file.txt .
        """,
    )

    parser.add_argument(
        "-c",
        "--context",
        required=True,
        help="Kubernetes context (e.g., qd for 青岛集群)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=300,
        help="Command timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--minio-only",
        action="store_true",
        help="Upload local file to MinIO tmp bucket instead of node copy",
    )
    parser.add_argument(
        "-o",
        "--object-name",
        help="Custom object name in MinIO (default: basename of local file)",
    )
    parser.add_argument(
        "--minio-threshold-mb",
        type=int,
        default=100,
        help="Auto-switch local upload to MinIO when file is larger than this size in MB (default: 100)",
    )
    parser.add_argument(
        "--force-node-upload",
        action="store_true",
        help="Disable MinIO auto-switch and always upload to node directly",
    )
    parser.add_argument(
        "source", help="Source path (local or remote in format node_ip:/path)"
    )
    parser.add_argument(
        "destination",
        nargs="?",
        help="Destination path (local or remote in format node_ip:/path)",
    )

    args = parser.parse_args()

    if args.minio_only:
        if args.destination is not None:
            print("Error: destination is not supported with --minio-only")
            sys.exit(1)
        success = upload_file_to_minio(
            context=args.context,
            local_path=args.source,
            object_name=args.object_name,
            timeout=args.timeout,
        )
        if success:
            print("Operation completed successfully")
            sys.exit(0)
        print("Operation failed")
        sys.exit(1)

    if args.destination is None:
        print("Error: destination is required unless --minio-only is used")
        sys.exit(1)

    source_is_remote = is_remote_path(args.source, allow_node_only=False)
    dest_is_remote = is_remote_path(args.destination, allow_node_only=True)

    if source_is_remote and dest_is_remote:
        print("Error: Both source and destination cannot be remote paths")
        sys.exit(1)

    if not source_is_remote and not dest_is_remote:
        print(
            "Error: At least one of source or destination must be a remote path (format: node_ip:/path)"
        )
        sys.exit(1)

    if source_is_remote:
        node_ip, remote_path = parse_remote_path(args.source)
        local_path = args.destination
        success = copy_file_from_node(
            context=args.context,
            node_ip=node_ip,
            remote_path=remote_path,
            local_path=local_path,
            timeout=args.timeout,
        )
    else:
        node_ip, remote_path = parse_remote_path(args.destination)
        local_path = args.source
        threshold_bytes = max(args.minio_threshold_mb, 0) * 1024 * 1024
        if not os.path.exists(local_path):
            print(f"Error: Local file '{local_path}' does not exist")
            sys.exit(1)

        if not os.path.isdir(local_path):
            file_size = os.path.getsize(local_path)
            if (
                not args.force_node_upload
                and threshold_bytes > 0
                and file_size > threshold_bytes
            ):
                object_name = args.object_name or choose_minio_object_name(
                    local_path, remote_path
                )
                print(
                    f"File size {file_size} bytes exceeds {threshold_bytes} bytes; "
                    "switching to MinIO tmp upload"
                )
                print(
                    "Note: destination node path will not be written in MinIO mode; "
                    f"object name: {object_name}"
                )
                success = upload_file_to_minio(
                    context=args.context,
                    local_path=local_path,
                    object_name=object_name,
                    timeout=args.timeout,
                )
            else:
                success = copy_file_to_node(
                    context=args.context,
                    node_ip=node_ip,
                    local_path=local_path,
                    remote_path=remote_path,
                    timeout=args.timeout,
                )
        else:
            success = copy_file_to_node(
                context=args.context,
                node_ip=node_ip,
                local_path=local_path,
                remote_path=remote_path,
                timeout=args.timeout,
            )

    if success:
        print("Operation completed successfully")
        sys.exit(0)
    else:
        print("Operation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
