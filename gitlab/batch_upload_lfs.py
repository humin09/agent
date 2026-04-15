#!/usr/bin/env python3
"""
批量 LFS 上传验证脚本
支持多线程处理多个模型目录
严谨验证所有命中 LFS 规则的文件是否在 MinIO 中存在
"""

import os
import hashlib
import subprocess
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import defaultdict

# LFS 规则后缀
LFS_SUFFIXES = {
    '.safetensors', '.bin', '.pt', '.pth', '.ckpt', '.h5', '.onnx', '.pb', '.tflite',
    '.pkl', '.joblib', '.msgpack', '.npy', '.npz', '.arrow', '.parquet',
    '.7z', '.bz2', '.gz', '.rar', '.tar', '.xz', '.zip', '.zst',
    '.json', '.md'  # 包括文档和配置文件
}

# 特殊模式：无后缀的 ONNX 权重文件
SPECIAL_PATTERNS = [
    'onnx__',
    'backbone.',
    'keypoint_',
]

class LFSBatchProcessor:
    def __init__(self, mc_path="/work/home/openaimodels/mc", minio_alias="xaminio"):
        self.mc = mc_path
        self.minio_alias = minio_alias
        self.results = {}

        # 设置日志
        log_file = f"/tmp/batch_lfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

    def is_lfs_file(self, filename):
        """检查文件是否命中 LFS 规则"""
        # 检查后缀
        if Path(filename).suffix.lower() in LFS_SUFFIXES:
            return True

        # 检查特殊模式（无后缀的 ONNX 权重文件等）
        for pattern in SPECIAL_PATTERNS:
            if pattern in filename:
                return True

        return False

    def scan_directory(self, directory):
        """扫描目录中所有 LFS 文件，返回 {oid: [file_paths]}"""
        self.logger.info(f"扫描目录: {directory}")

        files_by_oid = defaultdict(list)
        total_size = 0
        count = 0

        try:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if d != '.git']

                for f in files:
                    if self.is_lfs_file(f):
                        fpath = os.path.join(root, f)
                        try:
                            size = os.path.getsize(fpath)
                            with open(fpath, 'rb') as fp:
                                oid = hashlib.sha256(fp.read()).hexdigest()
                                rel_path = os.path.relpath(fpath, directory)
                                files_by_oid[oid].append(rel_path)
                                total_size += size
                                count += 1
                        except Exception as e:
                            self.logger.error(f"读取文件失败 {fpath}: {e}")
        except Exception as e:
            self.logger.error(f"扫描目录失败 {directory}: {e}")
            return None

        self.logger.info(f"  扫描完成: 找到 {count} 个LFS文件，{len(files_by_oid)} 个唯一OID，总大小 {total_size/1024/1024/1024:.2f} GB")
        return files_by_oid

    def verify_in_minio(self, oid):
        """检查 OID 是否存在于 MinIO 中"""
        path = f"{self.minio_alias}/gitlab-lfs-prod/{oid[0:2]}/{oid[2:4]}/{oid[4:]}"
        try:
            result = subprocess.run(
                [self.mc, 'stat', path],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.warning(f"检查 MinIO 失败 {oid[:16]}: {e}")
            return False

    def upload_file(self, src_file, oid):
        """上传文件到 MinIO"""
        dest_path = f"{self.minio_alias}/gitlab-lfs-prod/{oid[0:2]}/{oid[2:4]}/{oid[4:]}"
        try:
            result = subprocess.run(
                [self.mc, 'cp', src_file, dest_path],
                capture_output=True,
                timeout=300
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"上传失败 {oid[:16]}: {e}")
            return False

    def process_directory(self, directory, upload=False):
        """处理单个目录：扫描 + 验证 + 上传"""
        dir_name = os.path.basename(directory)
        self.logger.info(f"{'='*80}")
        self.logger.info(f"处理目录: {dir_name}")
        self.logger.info(f"路径: {directory}")

        # 扫描
        files_by_oid = self.scan_directory(directory)
        if files_by_oid is None:
            return {
                'directory': directory,
                'status': 'FAILED',
                'reason': '扫描失败',
                'total_oids': 0,
                'existing': 0,
                'missing': 0,
                'uploaded': 0
            }

        # 验证
        existing = 0
        missing = 0
        missing_oids = []

        self.logger.info(f"验证 {len(files_by_oid)} 个OID在MinIO中的存在情况...")
        for oid in files_by_oid.keys():
            if self.verify_in_minio(oid):
                existing += 1
            else:
                missing += 1
                missing_oids.append(oid)

        self.logger.info(f"  验证完成: 存在 {existing}/{len(files_by_oid)}, 缺失 {missing}/{len(files_by_oid)}")

        # 上传缺失文件
        uploaded = 0
        if upload and missing_oids:
            self.logger.info(f"开始上传 {missing} 个缺失的文件...")
            for oid in missing_oids:
                src_file = os.path.join(directory, files_by_oid[oid][0])
                if os.path.exists(src_file):
                    if self.upload_file(src_file, oid):
                        uploaded += 1
                        self.logger.info(f"  ✓ 上传成功: {oid[:16]}...")
                    else:
                        self.logger.error(f"  ✗ 上传失败: {oid[:16]}...")
                else:
                    self.logger.error(f"  ✗ 文件不存在: {src_file}")

        result = {
            'directory': directory,
            'name': dir_name,
            'status': 'OK' if missing == 0 else ('PARTIAL' if uploaded > 0 else 'MISSING'),
            'total_oids': len(files_by_oid),
            'existing': existing,
            'missing': missing,
            'uploaded': uploaded,
            'missing_oids': missing_oids[:5] if missing_oids else []  # 保存前5个缺失的OID用于报告
        }

        self.results[dir_name] = result
        return result

    def batch_process(self, directories, workers=12, upload=False):
        """批量处理多个目录"""
        self.logger.info(f"开始批量处理 {len(directories)} 个目录，并发数: {workers}")
        self.logger.info(f"上传模式: {'开启' if upload else '验证模式（不上传）'}")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.process_directory, d, upload): d
                for d in directories
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    result = future.result()
                    self.logger.info(f"[{completed}/{len(directories)}] 完成: {result['name']} - {result['status']}")
                except Exception as e:
                    self.logger.error(f"处理异常: {e}")

    def generate_report(self, output_file=None):
        """生成完整报告"""
        report_file = output_file or f"/tmp/batch_lfs_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_directories': len(self.results),
            'status_counts': defaultdict(int),
            'total_oids': 0,
            'total_existing': 0,
            'total_missing': 0,
            'total_uploaded': 0,
            'directories': self.results
        }

        for result in self.results.values():
            summary['status_counts'][result['status']] += 1
            summary['total_oids'] += result['total_oids']
            summary['total_existing'] += result['existing']
            summary['total_missing'] += result['missing']
            summary['total_uploaded'] += result['uploaded']

        with open(report_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        # 打印摘要
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"批量处理完成")
        self.logger.info(f"{'='*80}")
        self.logger.info(f"总目录数: {summary['total_directories']}")
        self.logger.info(f"状态分布: {dict(summary['status_counts'])}")
        self.logger.info(f"总OID数: {summary['total_oids']}")
        self.logger.info(f"  已存在: {summary['total_existing']}")
        self.logger.info(f"  缺失: {summary['total_missing']}")
        self.logger.info(f"  已上传: {summary['total_uploaded']}")
        self.logger.info(f"详细报告: {report_file}")

        return report_file


def main():
    import argparse

    parser = argparse.ArgumentParser(description='批量 LFS 验证上传脚本')
    parser.add_argument('--dirs', type=str, required=True, help='目录列表文件或逗号分隔的目录')
    parser.add_argument('--workers', type=int, default=12, help='并发数量（默认12）')
    parser.add_argument('--upload', action='store_true', help='是否执行上传（默认仅验证）')
    parser.add_argument('--mc', type=str, default='/work/home/openaimodels/mc', help='mc命令路径')

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

    # 执行批量处理
    processor = LFSBatchProcessor(mc_path=args.mc)
    processor.batch_process(directories, workers=args.workers, upload=args.upload)
    processor.generate_report()


if __name__ == '__main__':
    main()
