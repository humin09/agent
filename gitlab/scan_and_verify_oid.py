#!/usr/bin/env python3
"""
扫描目录中的LFS文件，计算OID，查询MinIO存在情况
生成OID-文件映射和详细报告
"""

import os
import hashlib
import json
import logging
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import subprocess
import sys

# LFS 规则后缀
LFS_SUFFIXES = {
    '.safetensors', '.bin', '.pt', '.pth', '.ckpt', '.h5', '.onnx', '.pb', '.tflite',
    '.pkl', '.joblib', '.msgpack', '.npy', '.npz', '.arrow', '.parquet',
    '.7z', '.bz2', '.gz', '.rar', '.tar', '.xz', '.zip', '.zst',
    '.json', '.md'
}

# 特殊模式
SPECIAL_PATTERNS = ['onnx__', 'backbone.', 'keypoint_']


class OIDScanner:
    def __init__(self):
        log_file = f"/tmp/scan_oid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(levelname)s: %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"日志文件: {log_file}")

        # 用于存储OID到文件路径的映射
        self.oid_to_files = defaultdict(list)  # {oid: [file_paths]}
        self.oid_sizes = {}  # {oid: size}
        self.total_scanned = 0

    def is_lfs_file(self, filename):
        """检查文件是否命中 LFS 规则"""
        if Path(filename).suffix.lower() in LFS_SUFFIXES:
            return True
        for pattern in SPECIAL_PATTERNS:
            if pattern in filename:
                return True
        return False

    def scan_directories(self, directory_list):
        """扫描多个目录，计算OID"""
        self.logger.info(f"开始扫描 {len(directory_list)} 个目录")

        for directory in directory_list:
            if not os.path.isdir(directory):
                self.logger.warning(f"目录不存在: {directory}")
                continue

            self.logger.info(f"扫描目录: {directory}")

            try:
                for root, dirs, files in os.walk(directory):
                    dirs[:] = [d for d in dirs if d != '.git']

                    for filename in files:
                        if self.is_lfs_file(filename):
                            filepath = os.path.join(root, filename)
                            try:
                                size = os.path.getsize(filepath)
                                with open(filepath, 'rb') as f:
                                    oid = hashlib.sha256(f.read()).hexdigest()
                                    rel_path = os.path.relpath(filepath, directory)
                                    self.oid_to_files[oid].append({
                                        'path': rel_path,
                                        'abs_path': filepath,
                                        'directory': directory
                                    })
                                    self.oid_sizes[oid] = size
                                    self.total_scanned += 1
                            except Exception as e:
                                self.logger.error(f"处理文件失败 {filepath}: {e}")
            except Exception as e:
                self.logger.error(f"扫描目录失败 {directory}: {e}")

        self.logger.info(f"扫描完成: 共 {self.total_scanned} 个文件，{len(self.oid_to_files)} 个唯一OID")

    def save_oid_mapping(self, output_file="/tmp/oid_mapping.json"):
        """保存OID到文件路径的映射"""
        mapping = {
            'timestamp': datetime.now().isoformat(),
            'total_files': self.total_scanned,
            'total_oids': len(self.oid_to_files),
            'oids': {}
        }

        for oid, files in self.oid_to_files.items():
            mapping['oids'][oid] = {
                'size': self.oid_sizes.get(oid, 0),
                'files': files
            }

        with open(output_file, 'w') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

        self.logger.info(f"OID映射已保存: {output_file}")
        return output_file

    def verify_in_minio(self, minio_host='vlogin34'):
        """查询MinIO中OID的存在情况"""
        self.logger.info(f"连接到MinIO服务器: {minio_host}")

        # OID存在情况
        existing_oids = set()
        missing_oids = set()

        # 使用SSH连接到vlogin34执行mc查询
        for i, oid in enumerate(self.oid_to_files.keys(), 1):
            path = f"xaminio/gitlab-lfs-prod/{oid[0:2]}/{oid[2:4]}/{oid[4:]}"
            try:
                # 通过SSH到vlogin34执行mc stat
                cmd = f"ssh {minio_host} '~/mc stat {path}'"
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    timeout=5
                )

                if result.returncode == 0:
                    existing_oids.add(oid)
                else:
                    missing_oids.add(oid)

                if i % 50 == 0:
                    self.logger.info(f"  已检查 {i}/{len(self.oid_to_files)} 个OID...")
            except Exception as e:
                self.logger.warning(f"检查OID失败 {oid[:16]}: {e}")
                missing_oids.add(oid)

        self.logger.info(f"MinIO查询完成: 存在 {len(existing_oids)}/{len(self.oid_to_files)}, 缺失 {len(missing_oids)}/{len(self.oid_to_files)}")

        return existing_oids, missing_oids

    def generate_report(self, existing_oids, missing_oids, output_file="/tmp/oid_report.json"):
        """生成最终报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_files': self.total_scanned,
            'total_oids': len(self.oid_to_files),
            'existing_count': len(existing_oids),
            'missing_count': len(missing_oids),
            'existing_oids': list(existing_oids),
            'missing_oids': list(missing_oids),
            'missing_details': {}
        }

        # 对于缺失的OID，提供详细信息（文件路径、大小等）
        for oid in missing_oids:
            files = self.oid_to_files[oid]
            report['missing_details'][oid] = {
                'size': self.oid_sizes.get(oid, 0),
                'file_count': len(files),
                'files': files
            }

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self.logger.info(f"报告已生成: {output_file}")

        # 打印摘要
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"扫描和验证完成")
        self.logger.info(f"{'='*80}")
        self.logger.info(f"总文件数: {self.total_scanned}")
        self.logger.info(f"唯一OID数: {len(self.oid_to_files)}")
        self.logger.info(f"  已存在: {len(existing_oids)}")
        self.logger.info(f"  缺失: {len(missing_oids)}")

        if missing_oids:
            total_missing_size = sum(
                self.oid_sizes.get(oid, 0) for oid in missing_oids
            )
            self.logger.info(f"缺失数据总大小: {total_missing_size / 1024 / 1024 / 1024:.2f} GB")

        return output_file


def main():
    import argparse

    parser = argparse.ArgumentParser(description='扫描目录并计算OID，查询MinIO存在情况')
    parser.add_argument('--dirs', type=str, required=True, help='目录列表文件或逗号分隔的目录')
    parser.add_argument('--minio-host', type=str, default='vlogin34', help='MinIO服务器SSH别名（默认vlogin34）')

    args = parser.parse_args()

    # 解析目录列表
    if os.path.isfile(args.dirs):
        with open(args.dirs) as f:
            directories = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        directories = [d.strip() for d in args.dirs.split(',')]

    # 过滤存在的目录
    directories = [d for d in directories if os.path.isdir(d)]

    if not directories:
        print("没有有效的目录")
        return

    # 执行扫描和验证
    scanner = OIDScanner()

    # 1. 扫描目录
    scanner.scan_directories(directories)

    # 2. 保存OID映射
    mapping_file = scanner.save_oid_mapping()

    # 3. 查询MinIO
    existing_oids, missing_oids = scanner.verify_in_minio(args.minio_host)

    # 4. 生成报告
    report_file = scanner.generate_report(existing_oids, missing_oids)

    print(f"\n✅ 完成!")
    print(f"OID映射文件: {mapping_file}")
    print(f"详细报告: {report_file}")


if __name__ == '__main__':
    main()
