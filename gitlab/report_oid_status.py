#!/usr/bin/env python3
"""
扫描目录计算OID，生成MinIO查询报告
复用upload_lfs.py的OID计算和检查逻辑
"""

import argparse
import hashlib
import os
import subprocess
import sys
import json
from datetime import datetime
from collections import defaultdict

MINIO_ALIAS = "xaminio"
BUCKET = "gitlab-lfs-prod"
MC = os.path.expanduser("~/mc")

LFS_EXTENSIONS = {
    ".safetensors", ".bin", ".pt", ".pth", ".ckpt", ".h5", ".onnx", ".pb", ".tflite",
    ".mlmodel", ".model", ".ot", ".ftz", ".gguf",
    ".pkl", ".joblib", ".msgpack", ".npy", ".npz", ".arrow", ".parquet",
    ".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip", ".zst",
    ".pickle", ".wasm",
}


def log(msg):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)


def oid_to_minio_path(oid: str) -> str:
    return f"{MINIO_ALIAS}/{BUCKET}/{oid[0:2]}/{oid[2:4]}/{oid[4:]}"


def check_oid_exists(oid: str) -> bool:
    try:
        r = subprocess.run(
            [MC, "stat", oid_to_minio_path(oid)],
            capture_output=True,
            timeout=5,
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
    """流式计算SHA256"""
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8 * 1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        log(f"ERROR: 计算SHA256失败 {filepath}: {e}")
        return None


def fmt_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024 / 1024:.2f}GB"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.0f}MB"
    return f"{size_bytes / 1024:.0f}KB"


def read_list_from_file(filepath: str) -> list:
    items = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                items.append(line)
    return items


def main():
    parser = argparse.ArgumentParser(description="扫描目录并生成OID状态报告")
    parser.add_argument("dirs", nargs="*", help="本地目录列表")
    parser.add_argument("-f", "--file", help="从文件读取目录路径")
    parser.add_argument("-o", "--output", default="/tmp/oid_report.json", help="输出报告文件")
    args = parser.parse_args()

    dirs = list(args.dirs)
    if args.file:
        dirs.extend(read_list_from_file(args.file))
    if not dirs:
        parser.print_help()
        sys.exit(1)

    log("=== 开始扫描目录并生成OID报告 ===")
    log(f"待扫描目录数: {len(dirs)}")
    log("")

    # 扫描所有文件和计算OID
    oid_to_files = defaultdict(list)
    oid_sizes = {}
    total_files = 0
    total_size = 0
    file_count_per_dir = {}

    for dir_idx, directory in enumerate(dirs, 1):
        if not os.path.isdir(directory):
            log(f"[{dir_idx}/{len(dirs)}] SKIP (不存在): {directory}")
            continue

        dir_name = os.path.basename(directory)
        log(f"[{dir_idx}/{len(dirs)}] 扫描: {dir_name}")

        dir_files = 0
        try:
            for root, _, files in os.walk(directory):
                for fname in files:
                    if has_lfs_extension(fname):
                        filepath = os.path.join(root, fname)
                        try:
                            size = os.path.getsize(filepath)
                            oid = sha256_file(filepath)

                            if oid:
                                rel_path = os.path.relpath(filepath, directory)
                                oid_to_files[oid].append({
                                    'directory': directory,
                                    'rel_path': rel_path,
                                    'abs_path': filepath,
                                    'size': size
                                })
                                oid_sizes[oid] = size
                                total_files += 1
                                total_size += size
                                dir_files += 1
                        except Exception as e:
                            log(f"  ERROR: {filepath}: {e}")
        except Exception as e:
            log(f"  ERROR: 扫描失败: {e}")

        file_count_per_dir[dir_name] = dir_files
        if dir_idx % 20 == 0:
            log(f"  进度: 已扫描{total_files}个文件")

    log(f"\n扫描完成: {total_files}个文件, {len(oid_to_files)}个唯一OID, 总大小{fmt_size(total_size)}")
    log("")

    # 查询MinIO
    log(f"开始查询MinIO (共{len(oid_to_files)}个OID)...")
    existing_oids = set()
    missing_oids = set()

    for i, oid in enumerate(oid_to_files.keys(), 1):
        if check_oid_exists(oid):
            existing_oids.add(oid)
        else:
            missing_oids.add(oid)

        if i % 100 == 0:
            log(f"  进度: {i}/{len(oid_to_files)} (已存在: {len(existing_oids)}, 缺失: {len(missing_oids)})")

    log(f"MinIO查询完成: 存在{len(existing_oids)}, 缺失{len(missing_oids)}")
    log("")

    # 计算缺失数据大小
    missing_size = sum(oid_sizes.get(oid, 0) for oid in missing_oids)

    # 生成报告
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_files': total_files,
        'total_size_bytes': total_size,
        'total_size_human': fmt_size(total_size),
        'total_oids': len(oid_to_files),
        'existing_count': len(existing_oids),
        'missing_count': len(missing_oids),
        'missing_size_bytes': missing_size,
        'missing_size_human': fmt_size(missing_size),
        'file_count_per_dir': file_count_per_dir,
        'missing_details': {}
    }

    # 详细缺失信息
    for oid in sorted(missing_oids):
        files = oid_to_files[oid]
        report['missing_details'][oid] = {
            'size': oid_sizes.get(oid, 0),
            'files': files
        }

    # 保存报告用JSON格式
    with open(args.output, 'w') as f:
        f.write(json.dumps(report, indent=2, ensure_ascii=False))

    log(f"报告已保存: {args.output}")
    log("")
    log("=== 最终统计 ===")
    log(f"总文件数: {total_files}")
    log(f"总大小: {fmt_size(total_size)}")
    log(f"唯一OID数: {len(oid_to_files)}")
    log(f"  已存在: {len(existing_oids)}")
    log(f"  缺失: {len(missing_oids)} (共{fmt_size(missing_size)})")

    if missing_oids:
        log("")
        log("缺失OID列表 (前20个):")
        for i, oid in enumerate(sorted(missing_oids)[:20], 1):
            files = oid_to_files[oid]
            size = oid_sizes.get(oid, 0)
            log(f"  {i}. {oid[:16]}... ({fmt_size(size)}, {len(files)}个文件)")

    log("")
    log(f"✅ 完成! 详细报告见: {args.output}")


if __name__ == "__main__":
    main()
