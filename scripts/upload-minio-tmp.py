#!/usr/bin/env python3
import argparse
import os
import shlex
import subprocess
import sys

MINIO_BUCKET = "tmp"
LOCAL_MINIO_ALIAS = "k8s-scp-local"
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


def format_command_for_log(cmd):
    return " ".join(shlex.quote(part) for part in cmd)


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

        print(f"File uploaded successfully to: {LOCAL_MINIO_ALIAS}/{MINIO_BUCKET}/{object_name}")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Upload file to Kubernetes cluster MinIO tmp bucket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Upload file to ks cluster MinIO tmp bucket:
    python upload-minio-tmp.py -c ks /tmp/large-file.tar.gz

  Upload with custom object name:
    python upload-minio-tmp.py -c ks /tmp/large-file.tar.gz -o my-custom-name.tar.gz

Supported contexts:
  ks (昆山), qd (青岛), dz (达州), zz (郑州), wh (武汉), sz (深圳)
        """,
    )

    parser.add_argument(
        "-c",
        "--context",
        required=True,
        help="Kubernetes context (e.g., ks for 昆山)",
    )
    parser.add_argument(
        "-o",
        "--object-name",
        help="Custom object name in MinIO (default: basename of local file)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=300,
        help="Command timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "file",
        help="Local file path to upload",
    )

    args = parser.parse_args()

    success = upload_file_to_minio(
        context=args.context,
        local_path=args.file,
        object_name=args.object_name,
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
