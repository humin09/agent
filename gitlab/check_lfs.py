#!/usr/bin/env python3
"""
排查 GitLab 仓库 LFS 指针对应 object 是否存在于 MinIO。

背景：GitLab 部分仓库的 LFS 指针映射的 object 在 MinIO 中丢失，
     导致 git clone / git lfs pull 失败。本脚本浅克隆仓库后提取
     LFS 指针，逐一检查对应 object 是否存在于 MinIO。

用法:
  # 直接传仓库 URL
  python3 check_lfs.py \\
    https://gitlab.scnet.cn:9002/model/sugon_scnet/DeepSeek-V3.2.git \\
    https://gitlab.scnet.cn:9002/model/sugon_scnet/Wan2.2-Animate-14B.git

  # 从文件读取仓库列表（每行一个 URL，# 开头为注释）
  python3 check_lfs.py -f repos.txt

执行环境: 本地（需要 mc 已配置 xaminio 别名）
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

MINIO_ALIAS = "xaminio"
BUCKET = "gitlab-lfs-prod"
MC = os.environ.get("MC", "mc")

GITLAB_USER = os.environ.get("GITLAB_USER", "root")
GITLAB_PASS = os.environ.get("GITLAB_PASS", "SugonHpc2024_pro")

LFS_EXTENSIONS = {
    ".safetensors", ".bin", ".pt", ".pth", ".ckpt", ".h5", ".onnx", ".pb",
    ".tflite", ".mlmodel", ".model", ".ot", ".ftz", ".gguf",
    ".pkl", ".joblib", ".msgpack", ".npy", ".npz", ".arrow", ".parquet",
    ".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip", ".zst",
}

LFS_POINTER_RE = re.compile(
    r"^version https://git-lfs\.github\.com/spec/v1\n"
    r"oid sha256:([0-9a-f]{64})\n"
    r"size (\d+)\n$",
    re.MULTILINE,
)


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


def fmt_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024 / 1024:.1f}GB"
    return f"{size_bytes / 1024 / 1024:.0f}MB"


def inject_credentials(url: str) -> str:
    return url.replace("https://", f"https://{quote(GITLAB_USER)}:{quote(GITLAB_PASS)}@")


def repo_name(url: str) -> str:
    return url.rstrip("/").rstrip(".git").rsplit("/", 1)[-1]


def extract_lfs_pointers(clone_dir: str) -> list[tuple[str, str, int]]:
    """遍历克隆目录，提取 LFS 指针: [(相对路径, oid, size), ...]"""
    pointers = []
    for root, _, files in os.walk(clone_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, clone_dir)
            if rel.startswith(".git"):
                continue
            if not has_lfs_extension(rel):
                continue
            try:
                with open(fpath, "r", errors="ignore") as f:
                    content = f.read(512)
                m = LFS_POINTER_RE.match(content)
                if m:
                    pointers.append((rel, m.group(1), int(m.group(2))))
            except Exception:
                continue
    return pointers


def read_list_from_file(filepath: str) -> list[str]:
    items = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                items.append(line)
    return items


def main():
    parser = argparse.ArgumentParser(
        description="排查 GitLab 仓库 LFS object 缺失",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("repos", nargs="*", help="GitLab 仓库 URL 列表")
    parser.add_argument("-f", "--file", help="从文件读取仓库 URL（每行一个）")
    parser.add_argument("-j", "--jobs", type=int, default=16, help="mc stat 并发数（默认 16）")
    args = parser.parse_args()

    repos = list(args.repos)
    if args.file:
        repos.extend(read_list_from_file(args.file))
    if not repos:
        parser.print_help()
        sys.exit(1)

    all_results = {}

    for url in repos:
        name = repo_name(url)
        print(f"\n{'=' * 60}")
        print(f"排查: {name}")
        print(f"{'=' * 60}")

        tmpdir = tempfile.mkdtemp(prefix=f"lfs_{name}_")
        clone_url = inject_credentials(url if url.endswith(".git") else url + ".git")

        try:
            env = os.environ.copy()
            env["GIT_LFS_SKIP_SMUDGE"] = "1"
            print("  克隆中...")
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, tmpdir + "/repo"],
                capture_output=True, timeout=600, env=env,
            )
            clone_path = tmpdir + "/repo"

            pointers = extract_lfs_pointers(clone_path)
            print(f"  找到 {len(pointers)} 个 LFS 指针")

            if not pointers:
                all_results[name] = {"total": 0, "exists": 0, "missing": []}
                continue

            missing = []
            results = {}
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                futures = {pool.submit(check_oid_exists, oid): (filename, oid, size)
                           for filename, oid, size in pointers}
                for fut in as_completed(futures):
                    filename, oid, size = futures[fut]
                    results[(filename, oid, size)] = fut.result()
            for i, (filename, oid, size) in enumerate(pointers, 1):
                exists = results[(filename, oid, size)]
                mark = "OK" if exists else "MISS"
                print(f"  [{i}/{len(pointers)}] {mark} {filename} ({oid[:12]}...) {fmt_size(size)}")
                if not exists:
                    missing.append((oid, filename, size))

            all_results[name] = {
                "total": len(pointers),
                "exists": len(pointers) - len(missing),
                "missing": missing,
            }
        except subprocess.TimeoutExpired:
            print("  克隆超时!")
            all_results[name] = {"total": 0, "exists": 0, "missing": [], "error": "clone timeout"}
        except Exception as e:
            print(f"  错误: {e}")
            all_results[name] = {"total": 0, "exists": 0, "missing": [], "error": str(e)}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # 汇总
    print(f"\n\n{'=' * 70}")
    print("汇总")
    print(f"{'=' * 70}")
    print(f"{'仓库':<45} {'LFS总数':>8} {'已有':>6} {'缺失':>6}  {'状态'}")
    print("-" * 70)

    total_missing_all = 0
    for url in repos:
        name = repo_name(url)
        r = all_results.get(name, {})
        if "error" in r:
            print(f"{name:<45} {'ERROR':>8}  {r['error']}")
            continue
        total = r["total"]
        exists = r["exists"]
        miss = len(r["missing"])
        total_missing_all += miss
        status = "COMPLETE" if miss == 0 else "INCOMPLETE"
        print(f"{name:<45} {total:>8} {exists:>6} {miss:>6}  {status}")

    # 缺失明细
    for url in repos:
        name = repo_name(url)
        r = all_results.get(name, {})
        if r.get("missing"):
            print(f"\n{name} ({len(r['missing'])} 个缺失):")
            for oid, filename, size in r["missing"]:
                print(f"  {oid}  {filename}  ({fmt_size(size)})")

    print(f"\n共 {total_missing_all} 个 object 缺失")
    sys.exit(1 if total_missing_all > 0 else 0)


if __name__ == "__main__":
    main()
