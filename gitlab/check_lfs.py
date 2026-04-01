#!/usr/bin/env python3
"""
混合策略：先用 API 快速检查第一个 LFS 指针，
如果第一个缺失直接标记；如果第一个存在再 clone 检查全部！
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, urlparse
import requests

requests.packages.urllib3.disable_warnings()

MINIO_ALIAS = "xaminio"
BUCKET = "gitlab-lfs-prod"
MC = os.environ.get("MC", "mc")

GITLAB_URL = "https://gitlab.scnet.cn:9002"
GITLAB_USER = os.environ.get("GITLAB_USER", "root")
GITLAB_PASS = os.environ.get("GITLAB_PASS", "SugonHpc2024_pro")

LFS_EXTENSIONS = {
    ".safetensors",
    ".bin",
    ".pt",
    ".pth",
    ".ckpt",
    ".h5",
    ".onnx",
    ".pb",
    ".tflite",
    ".mlmodel",
    ".model",
    ".ot",
    ".ftz",
    ".gguf",
    ".pkl",
    ".pickle",
    ".joblib",
    ".msgpack",
    ".npy",
    ".npz",
    ".arrow",
    ".parquet",
    ".7z",
    ".bz2",
    ".gz",
    ".rar",
    ".tar",
    ".tgz",
    ".xz",
    ".zip",
    ".zst",
    ".wasm",
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
            capture_output=True,
            timeout=30,
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
    return url.replace(
        "https://", f"https://{quote(GITLAB_USER)}:{quote(GITLAB_PASS)}@"
    )


def get_project_id(repo_url: str) -> str:
    path = repo_url.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parsed = urlparse(path)
    project_path = parsed.path.lstrip("/")
    return quote(project_path, safe="")


def list_repo_files(project_id: str, ref="main", path="") -> list:
    files = []
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/tree"
    params = {"ref": ref, "path": path, "per_page": 100, "recursive": True}

    try:
        r = requests.get(
            url,
            params=params,
            auth=(GITLAB_USER, GITLAB_PASS),
            verify=False,
            timeout=60,
        )
        r.raise_for_status()
        items = r.json()

        for item in items:
            if item["type"] == "blob":
                files.append(item["path"])

    except Exception:
        pass

    return files


def get_file_content(project_id: str, file_path: str, ref="main") -> str:
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/files/{quote(file_path, safe='')}/raw"
    params = {"ref": ref}

    try:
        r = requests.get(
            url,
            params=params,
            auth=(GITLAB_USER, GITLAB_PASS),
            verify=False,
            timeout=60,
        )
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return ""


def get_first_lfs_pointer_api(project_id: str) -> tuple[str, str, int] | None:
    """通过 API 快速获取第一个 LFS 指针"""
    for ref in ["main", "master"]:
        files = list_repo_files(project_id, ref=ref)
        if files:
            break

    if not files:
        return None

    lfs_files = [f for f in files if has_lfs_extension(f)]
    if not lfs_files:
        return None

    for file_path in lfs_files:
        content = get_file_content(project_id, file_path, ref=ref)
        if content:
            m = LFS_POINTER_RE.match(content)
            if m:
                return (file_path, m.group(1), int(m.group(2)))

    return None


def extract_lfs_pointers_clone(clone_dir: str) -> list[tuple[str, str, int]]:
    """clone 后提取所有 LFS 指针"""
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


def repo_name(url: str) -> str:
    path = url.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path.rsplit("/", 1)[-1]


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
        description="混合策略：API 快速预检 + clone 详细检查",
    )
    parser.add_argument("repos", nargs="*", help="GitLab 仓库 URL 列表")
    parser.add_argument("-f", "--file", help="从文件读取仓库 URL（每行一个）")
    parser.add_argument(
        "-j", "--jobs", type=int, default=16, help="mc stat 并发数（默认 16）"
    )
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

        try:
            project_id = get_project_id(url)

            # 步骤 1：API 快速拿第一个 LFS 指针
            print("  [1/3] API 快速预检...")
            first_pointer = get_first_lfs_pointer_api(project_id)

            if not first_pointer:
                print("  无 LFS 文件")
                all_results[name] = {"total": 0, "exists": 0, "missing": []}
                continue

            first_filename, first_oid, first_size = first_pointer
            print(f"  第一个 LFS 文件: {first_filename} ({first_oid[:12]}...)")

            # 步骤 2：检查第一个指针是否存在
            print("  [2/3] 检查第一个 object...")
            first_exists = check_oid_exists(first_oid)

            if not first_exists:
                print("  第一个 object 缺失 → 直接标记为全部缺失（跳过 clone）")
                all_results[name] = {
                    "total": 1,
                    "exists": 0,
                    "missing": [(first_oid, first_filename, first_size)],
                    "skipped_clone": True,
                }
                continue

            print("  第一个 object 存在 → 继续 clone 检查全部")

            # 步骤 3：clone 仓库详细检查全部
            print("  [3/3] Clone 仓库详细检查...")
            tmpdir = tempfile.mkdtemp(prefix=f"lfs_{name}_")
            clone_url = inject_credentials(
                url if url.endswith(".git") else url + ".git"
            )

            env = os.environ.copy()
            env["GIT_LFS_SKIP_SMUDGE"] = "1"
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, tmpdir + "/repo"],
                capture_output=True,
                timeout=600,
                env=env,
            )
            clone_path = tmpdir + "/repo"

            pointers = extract_lfs_pointers_clone(clone_path)
            print(f"  找到 {len(pointers)} 个 LFS 指针")

            if not pointers:
                all_results[name] = {"total": 0, "exists": 0, "missing": []}
                shutil.rmtree(tmpdir, ignore_errors=True)
                continue

            missing = []
            results = {}
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                futures = {
                    pool.submit(check_oid_exists, oid): (filename, oid, size)
                    for filename, oid, size in pointers
                }
                for fut in as_completed(futures):
                    filename, oid, size = futures[fut]
                    results[(filename, oid, size)] = fut.result()
            for i, (filename, oid, size) in enumerate(pointers, 1):
                exists = results[(filename, oid, size)]
                mark = "OK" if exists else "MISS"
                print(
                    f"  [{i}/{len(pointers)}] {mark} {filename} ({oid[:12]}...) {fmt_size(size)}"
                )
                if not exists:
                    missing.append((oid, filename, size))

            all_results[name] = {
                "total": len(pointers),
                "exists": len(pointers) - len(missing),
                "missing": missing,
            }

            shutil.rmtree(tmpdir, ignore_errors=True)

        except Exception as e:
            print(f"  错误: {e}")
            import traceback

            traceback.print_exc()
            all_results[name] = {
                "total": 0,
                "exists": 0,
                "missing": [],
                "error": str(e),
            }

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
        if r.get("skipped_clone"):
            status += " (SKIPPED CLONE)"
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
