#!/usr/bin/env python3
"""
将本地目录中的 LFS 文件计算 sha256 后上传到 MinIO。

背景：GitLab 部分仓库的 LFS 指针映射的 object 在 MinIO 中丢失，
     需要从已下载的本地文件补充上传。本脚本扫描指定目录，按 LFS
     后缀规则筛选文件，计算 sha256 得到 OID，上传到 MinIO 对应路径。

用法:
  # 直接传目录
  python3 /tmp/upload_lfs.py \\
    /work/home/openaimodels/ai_community/model/Qwen/Qwen3.5-27B \\
    /work/home/openaimodels/ai_community/re_model/deepseek-ai/Janus-Pro-7B

  # 从文件读取目录列表，并发 16
  python3 /tmp/upload_lfs.py -f /tmp/dirs.txt -j 16

  # dry-run 仅检查不上传
  python3 /tmp/upload_lfs.py --dry-run /path/to/model

执行环境: xa-login（需要 ~/mc 已配置 xaminio 别名）
固定路径: /tmp/upload_lfs.py
"""

import argparse
import hashlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

MINIO_ALIAS = "xaminio"
BUCKET = "gitlab-lfs-prod"
MC = os.path.expanduser("~/mc")

LFS_EXTENSIONS = {
    ".safetensors", ".bin", ".pt", ".pth", ".ckpt", ".h5", ".onnx", ".pb",
    ".tflite", ".mlmodel", ".model", ".ot", ".ftz", ".gguf",
    ".pkl", ".joblib", ".msgpack", ".npy", ".npz", ".arrow", ".parquet",
    ".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip", ".zst",
}


def oid_to_minio_path(oid: str) -> str:
    return f"{MINIO_ALIAS}/{BUCKET}/{oid[0:2]}/{oid[2:4]}/{oid[4:]}"


def check_oid_exists(oid: str) -> bool:
    try:
        r = subprocess.run(
            [MC, "stat", oid_to_minio_path(oid)],
            capture_output=True, timeout=30,
        )
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def has_lfs_extension(filepath: str) -> bool:
    name = filepath.lower()
    if ".tar." in name:
        return True
    _, ext = os.path.splitext(name)
    return ext in LFS_EXTENSIONS


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def fmt_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024 / 1024:.1f}GB"
    return f"{size_bytes / 1024 / 1024:.0f}MB"


def read_list_from_file(filepath: str) -> list[str]:
    items = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                items.append(line)
    return items


def upload_one_file(filepath: str, dry_run: bool) -> dict:
    """处理单个文件：计算 sha256，检查是否存在，上传。"""
    result = {"file": filepath, "status": "unknown", "oid": "", "size": 0}
    try:
        result["size"] = os.path.getsize(filepath)
        oid = sha256_file(filepath)
        result["oid"] = oid
        minio_path = oid_to_minio_path(oid)

        if check_oid_exists(oid):
            result["status"] = "skip"
            return result

        if dry_run:
            result["status"] = "would_upload"
            return result

        r = subprocess.run(
            [MC, "cp", filepath, minio_path],
            capture_output=True, timeout=600,
        )
        result["status"] = "ok" if r.returncode == 0 else "fail"
        if r.returncode != 0:
            result["error"] = r.stderr.decode(errors="replace").strip()
    except Exception as e:
        result["status"] = "fail"
        result["error"] = str(e)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="上传本地 LFS 文件到 MinIO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("dirs", nargs="*", help="本地目录列表")
    parser.add_argument("-f", "--file", help="从文件读取目录路径（每行一个）")
    parser.add_argument("-j", "--jobs", type=int, default=12, help="并发数（默认 12）")
    parser.add_argument("--dry-run", action="store_true", help="仅检查不上传")
    args = parser.parse_args()

    dirs = list(args.dirs)
    if args.file:
        dirs.extend(read_list_from_file(args.file))
    if not dirs:
        parser.print_help()
        sys.exit(1)

    parallel = args.jobs
    dry_run = args.dry_run
    log_file = f"/tmp/upload_lfs_{datetime.now():%Y%m%d_%H%M%S}.log"

    def log(msg):
        line = f"[{datetime.now():%H:%M:%S}] {msg}"
        print(line, flush=True)
        with open(log_file, "a") as f:
            f.write(line + "\n")

    log("=== LFS 对象补充上传 ===")
    log(f"模式: {'DRY-RUN（仅检查不上传）' if dry_run else '正式上传'}")
    log(f"并发数: {parallel}")
    log(f"目标: {MINIO_ALIAS}/{BUCKET}")
    log("")

    # 收集文件
    all_files = []
    for d in dirs:
        if not os.path.isdir(d):
            log(f"目录不存在，跳过: {d}")
            continue
        log(f"扫描目录: {d}")
        for root, _, files in os.walk(d):
            for fname in files:
                if has_lfs_extension(fname):
                    all_files.append(os.path.join(root, fname))

    log(f"\n共发现 {len(all_files)} 个 LFS 文件，开始并发处理（并发={parallel}）...\n")

    uploaded = skipped = failed = 0

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {pool.submit(upload_one_file, f, dry_run): f for f in all_files}
        for future in as_completed(futures):
            r = future.result()
            name = os.path.basename(r["file"])
            size_str = fmt_size(r["size"])
            oid_short = r["oid"][:12] + "..." if r["oid"] else "?"

            if r["status"] == "skip":
                log(f"  SKIP (已存在) {name} [{size_str}] oid={oid_short}")
                skipped += 1
            elif r["status"] == "would_upload":
                log(f"  WOULD UPLOAD {name} [{size_str}] oid={oid_short}")
            elif r["status"] == "ok":
                log(f"  OK {name} [{size_str}] oid={oid_short}")
                uploaded += 1
            else:
                log(f"  FAIL {name} [{size_str}] {r.get('error', '')}")
                failed += 1

    log("")
    log("=== 完成统计 ===")
    log(f"扫描文件: {len(all_files)}")
    log(f"已存在跳过: {skipped}")
    log(f"上传成功: {uploaded}")
    log(f"上传失败: {failed}")
    log(f"日志文件: {log_file}")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
