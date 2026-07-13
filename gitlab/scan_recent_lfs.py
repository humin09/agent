#!/usr/bin/env python3
"""扫描最近N个月GitLab项目，多集群(xa/ly/ks/qd) LFS完备性检查。

输出:
  1. MD 报告: 每个LFS项目一行，各集群 ✅/❌
  2. JSON 同步计划: 按集群列出缺失的 OID (去重)

用法:
    python3 ~/agent/gitlab/scan_recent_lfs.py               # 默认3个月, xa/ly/ks/qd
    python3 ~/agent/gitlab/scan_recent_lfs.py -m 1          # 最近1个月
    python3 ~/agent/gitlab/scan_recent_lfs.py -c xa ks       # 只检查 xa+ks
    python3 ~/agent/gitlab/scan_recent_lfs.py --skip-step1   # 复用缓存的项目列表
    python3 ~/agent/gitlab/scan_recent_lfs.py --skip-step2   # 复用缓存的LFS候选
    python3 ~/agent/gitlab/scan_recent_lfs.py --list-only    # 仅列项目，不检查
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

GITLAB_URL = "https://gitlab.scnet.cn:9002"
GITLAB_USER = os.environ.get("GITLAB_USER", "root")
GITLAB_PASS = os.environ.get("GITLAB_PASS", "SugonHpc2024_pro")

DEFAULT_CLUSTERS = ["xa", "ly", "ks", "qd"]
BUCKET = "gitlab-lfs-prod"
MC = "mc"

LFS_EXTENSIONS = {
    ".safetensors", ".bin", ".pt", ".pth", ".ckpt", ".h5", ".onnx", ".pb",
    ".tflite", ".mlmodel", ".model", ".ot", ".ftz", ".gguf",
    ".pkl", ".pickle", ".joblib", ".msgpack", ".npy", ".npz", ".arrow", ".parquet",
    ".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip", ".zst", ".wasm",
}

LFS_POINTER_RE = re.compile(
    r"^version https://git-lfs\.github\.com/spec/v1\n"
    r"oid sha256:([0-9a-f]{64})\n"
    r"size (\d+)\n$",
    re.MULTILINE,
)

CACHE_DIR = Path(tempfile.gettempdir())
NS_WHITELIST = {"model", "dataset"}
NS_BLACKLIST = {"skills"}


def oid_path(oid: str, alias: str) -> str:
    return f"{alias}/{BUCKET}/{oid[0:2]}/{oid[2:4]}/{oid[4:]}"


def check_oids_batch(oid: str, clusters: list[str]) -> dict[str, bool]:
    out = {}
    for alias in clusters:
        try:
            r = subprocess.run(
                [MC, "stat", "--json", oid_path(oid, alias)],
                capture_output=True, timeout=30,
            )
            out[alias] = r.returncode == 0
        except subprocess.TimeoutExpired:
            out[alias] = False
    return out


def has_lfs_ext(p: str) -> bool:
    name = p.lower()
    if ".tar." in name:
        return True
    _, ext = os.path.splitext(name)
    return ext in LFS_EXTENSIONS


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str):
    print(f"[{ts()}] {msg}", flush=True)


# ── Step 1: curl 并发分页 ─────────────────────────────────────────────

def fetch_page_curl(page: int, after: str, per_page: int = 100):
    out_path = CACHE_DIR / f"gitlab_page_{page}.json"
    url = (
        f"{GITLAB_URL}/api/v4/projects"
        f"?created_after={after}&per_page={per_page}&page={page}"
        f"&order_by=created_at&sort=desc&imported=false"
    )
    try:
        r = subprocess.run(
            [
                "curl", "-sk", "--max-time", "60",
                "-o", str(out_path),
                "-u", f"{GITLAB_USER}:{GITLAB_PASS}",
                url,
            ],
            capture_output=True, timeout=90,
        )
        if r.returncode != 0 or not out_path.exists() or out_path.stat().st_size < 2:
            return page, None
        with open(out_path) as f:
            data = json.load(f)
        return page, data if isinstance(data, list) else None
    except Exception:
        return page, None


def step1_fetch_all(months: int) -> tuple[list[dict], str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    cutoff_date = cutoff.strftime("%Y-%m-%d")
    log(f"Step 1: 下载最近 {months} 个月项目列表 (created_after={cutoff_date})")

    projects = []
    page = 1
    max_page = 400

    while page <= max_page:
        batch_size = min(20, max_page - page + 1)
        pages = list(range(page, page + batch_size))
        results = {}

        with ThreadPoolExecutor(max_workers=20) as pool:
            futs = {pool.submit(fetch_page_curl, p, after): p for p in pages}
            for fut in as_completed(futs):
                p, data = fut.result()
                results[p] = data

        all_empty = True
        for p in pages:
            data = results.get(p)
            if not data:
                continue
            all_empty = False
            valid = [x for x in data if x.get("created_at", "") >= after]
            projects.extend(valid)

        for p in pages:
            (CACHE_DIR / f"gitlab_page_{p}.json").unlink(missing_ok=True)

        if all_empty:
            log(f"  page {page} 空，停止")
            break

        log(f"  已获取 {len(projects)} 个项目 (page={pages[-1]})")
        page = pages[-1] + 1

    cache_file = CACHE_DIR / f"gitlab_projects_{months}m.json"
    with open(cache_file, "w") as f:
        json.dump(projects, f, ensure_ascii=False)
    log(f"Step 1 完成: {len(projects)} 个项目 -> {cache_file}")
    return projects, after


def step1_load_cache(months: int) -> list[dict] | None:
    cache_file = CACHE_DIR / f"gitlab_projects_{months}m.json"
    if not cache_file.exists():
        return None
    with open(cache_file) as f:
        return json.load(f)


# ── Step 2: 过滤 LFS 项目 ────────────────────────────────────────────

def check_gitattributes(project: dict) -> bool:
    pid = project["id"]
    ref = project.get("default_branch") or "main"
    try:
        r = subprocess.run(
            [
                "curl", "-sk", "--max-time", "15",
                "-u", f"{GITLAB_USER}:{GITLAB_PASS}",
                f"{GITLAB_URL}/api/v4/projects/{pid}/repository/files/.gitattributes?ref={ref}",
            ],
            capture_output=True, timeout=20,
        )
        if r.returncode != 0 or not r.stdout:
            return False
        data = json.loads(r.stdout)
        content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
        return "filter=lfs" in content
    except Exception:
        return False


def step2_filter_lfs(projects: list[dict], jobs: int = 16) -> list[dict]:
    ns_match = []
    skipped = 0
    other = []
    for p in projects:
        top_ns = p.get("namespace", {}).get("full_path", "").split("/")[0]
        if top_ns in NS_WHITELIST:
            ns_match.append(p)
        elif top_ns in NS_BLACKLIST:
            skipped += 1
        else:
            other.append(p)

    log(f"Step 2: namespace命中 {len(ns_match)} 个 (ns={NS_WHITELIST}), 跳过 {skipped} 个 (ns={NS_BLACKLIST}), 检查 {len(other)} 个")

    lfs_cands = list(ns_match)
    done = 0
    if other:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futs = {pool.submit(check_gitattributes, p): p for p in other}
            for fut in as_completed(futs):
                done += 1
                proj = futs[fut]
                try:
                    if fut.result():
                        lfs_cands.append(proj)
                except Exception:
                    pass
                if done % 200 == 0 or done == len(other):
                    log(f"  进度 {done}/{len(other)}  LFS候选={len(lfs_cands)}")

    lfs_cands.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    cache_file = CACHE_DIR / "gitlab_lfs_candidates.json"
    with open(cache_file, "w") as f:
        json.dump(lfs_cands, f, ensure_ascii=False)
    log(f"Step 2 完成: {len(lfs_cands)} 个 LFS 项目 -> {cache_file}")
    return lfs_cands


# ── Step 3: Clone + mc stat ──────────────────────────────────────────

def _clone_and_extract(project: dict):
    try:
        name = project["name"]
        http_url = project.get("http_url_to_repo", "")
        if not http_url:
            return project, []
        tmpdir = tempfile.mkdtemp(prefix=f"lfs_scan_{name[:30]}_")
        clone_url = http_url.replace(
            "https://", f"https://{quote(GITLAB_USER)}:{quote(GITLAB_PASS)}@"
        )
        if not clone_url.endswith(".git"):
            clone_url += ".git"
        env = os.environ.copy()
        env["GIT_LFS_SKIP_SMUDGE"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, os.path.join(tmpdir, "repo")],
            capture_output=True, timeout=300, env=env,
        )
        pointers = []
        repo_dir = os.path.join(tmpdir, "repo")
        if os.path.isdir(repo_dir):
            for root, _, files in os.walk(repo_dir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, repo_dir)
                    if rel.startswith(".git") or not has_lfs_ext(rel):
                        continue
                    try:
                        with open(fpath, "r", errors="ignore") as f:
                            content = f.read(512)
                        m = LFS_POINTER_RE.match(content)
                        if m:
                            pointers.append((rel, m.group(1), int(m.group(2))))
                    except Exception:
                        continue
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pointers = []
    return project, pointers


def step3_check_lfs(lfs_projects: list[dict], clusters: list[str],
                    jobs: int = 16, cutoff: str = "", months: int = 3,
                    out_md: str = "", out_json: str = ""):
    log(f"Step 3: Clone + mc stat (jobs={jobs}, clusters={clusters}, 项目={len(lfs_projects)})")

    log(f"并发 clone 所有项目 (workers={min(jobs, 8)})...")
    project_pointers = {}
    done_clone = 0
    with ThreadPoolExecutor(max_workers=min(jobs, 8)) as pool:
        futs = {pool.submit(_clone_and_extract, p): p for p in lfs_projects}
        for fut in as_completed(futs):
            p, pointers = fut.result()
            done_clone += 1
            ns = p.get("namespace", {}).get("full_path", "")
            project_pointers[f"{ns}/{p['name']}"] = pointers
            if done_clone % 50 == 0 or done_clone == len(lfs_projects):
                n_with = sum(1 for v in project_pointers.values() if v)
                log(f"  clone 进度 {done_clone}/{len(lfs_projects)}  有LFS指针={n_with}")

    results = []
    for p in lfs_projects:
        ns = p.get("namespace", {}).get("full_path", "")
        full_name = f"{ns}/{p['name']}"
        pointers = project_pointers.get(full_name, [])
        log(f"  {full_name}: {len(pointers)} 对象")

        if not pointers:
            results.append({
                "project": full_name, "created": p.get("created_at", "")[:10],
                "lfs_count": 0, "status": "无LFS对象",
                "cluster_stats": {c: {"miss": 0} for c in clusters},
                "missing_items": [],
            })
            continue

        cluster_stats = {c: {"total": 0, "exist": 0, "miss": 0} for c in clusters}
        missing_items = []

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futs = {
                pool.submit(check_oids_batch, oid, clusters): (rel, oid, size)
                for rel, oid, size in pointers
            }
            res_map = {}
            for fut in as_completed(futs):
                rel, oid, size = futs[fut]
                try:
                    res_map[(rel, oid, size)] = fut.result()
                except Exception:
                    res_map[(rel, oid, size)] = {c: False for c in clusters}

        for rel, oid, size in pointers:
            exists_map = res_map[(rel, oid, size)]
            for c in clusters:
                cluster_stats[c]["total"] += 1
                if exists_map.get(c):
                    cluster_stats[c]["exist"] += 1
                else:
                    cluster_stats[c]["miss"] += 1
            miss_clusters = [c for c in clusters if not exists_map.get(c)]
            if miss_clusters:
                missing_items.append({
                    "oid": oid, "file": rel,
                    "missing_in": miss_clusters,
                })

        all_ok = all(cluster_stats[c]["miss"] == 0 for c in clusters)
        results.append({
            "project": full_name,
            "created": p.get("created_at", "")[:10],
            "lfs_count": len(pointers),
            "status": "COMPLETE" if all_ok else "INCOMPLETE",
            "cluster_stats": cluster_stats,
            "missing_items": missing_items,
            "missing_count": len(missing_items),
        })

    # ── 生成 MD ─────────────────────────────────────────────
    with_lfs = [r for r in results if r['lfs_count'] > 0]
    no_lfs = [r for r in results if r['lfs_count'] == 0]
    scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = [
        "# GitLab LFS 完备性报告",
        "",
        f"- 扫描时间: {scan_time}",
        f"- 时间范围: 最近 {months} 个月 ({cutoff[:10]} ~ 今)",
        f"- 集群: {', '.join(clusters)}",
        f"- LFS 项目总数: {len(results)}  (有LFS {len(with_lfs)}, 无LFS {len(no_lfs)})",
        "",
        "## 有 LFS 对象的项目",
        "",
        "| 项目 | 创建时间 | LFS数 | " + " | ".join(clusters) + " |",
        "|" + "---|" * (3 + len(clusters)),
    ]

    for r in with_lfs:
        marks = []
        for c in clusters:
            if r['cluster_stats'][c]['miss'] > 0:
                marks.append("❌")
            else:
                marks.append("✅")
        md.append(f"| {r['project']} | {r['created']} | {r['lfs_count']} | " +
                  " | ".join(marks) + " |")

    md.extend([
        "",
        "## 无 LFS 对象的项目",
        "",
        "| 项目 | 创建时间 |",
        "|------|---------|",
    ])
    for r in no_lfs:
        md.append(f"| {r['project']} | {r['created']} |")

    md.extend(["", "## 统计", ""])
    for c in clusters:
        ok = sum(1 for r in with_lfs if r['cluster_stats'][c]['miss'] == 0)
        miss = len(with_lfs) - ok
        md.append(f"- {c}: 完备 {ok}, 缺失 {miss}")

    out_md_path = out_md or "/tmp/scan_recent_lfs_report.md"
    with open(out_md_path, "w") as f:
        f.write("\n".join(md) + "\n")

    # ── 生成同步 JSON ─────────────────────────────────────
    sync_plan = {c: {} for c in clusters}
    for r in results:
        for item in r.get('missing_items', []):
            for c in item['missing_in']:
                if item['oid'] not in sync_plan[c]:
                    sync_plan[c][item['oid']] = {
                        "oid": item['oid'],
                        "project": r['project'],
                        "file": item['file'],
                    }

    json_out = {
        "_summary": {
            "scan_time": scan_time,
            "cutoff": cutoff,
            "months": months,
            "total_lfs_projects": len(with_lfs),
        }
    }
    for c in clusters:
        json_out[c] = {
            "missing_count": len(sync_plan[c]),
            "oids": sync_plan[c],
        }

    out_json_path = out_json or "/tmp/scan_recent_lfs_sync.json"
    with open(out_json_path, "w") as f:
        json.dump(json_out, f, indent=2, ensure_ascii=False)

    log("")
    log(f"✅ 完成")
    log(f"   MD:   {out_md_path}")
    log(f"   JSON: {out_json_path}")
    log("")

    for c in clusters:
        n = len(sync_plan[c])
        log(f"   {c}: {n} OID 待同步" if n > 0 else f"   {c}: 完备")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="扫描最近N个月GitLab项目 + 多集群LFS完备性检查",
    )
    parser.add_argument("-m", "--months", type=int, default=3)
    parser.add_argument("-c", "--clusters", nargs="+", default=DEFAULT_CLUSTERS)
    parser.add_argument("-j", "--jobs", type=int, default=16)
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--max", type=int, default=0)
    parser.add_argument("--skip-step1", action="store_true")
    parser.add_argument("--skip-step2", action="store_true")
    parser.add_argument("-o", "--output", default="~/agent/reports/scan_recent_lfs_report.md")
    parser.add_argument("--json-output", default="~/agent/logs/scan_recent_lfs_sync.json")
    args = parser.parse_args()

    args.output = os.path.expanduser(args.output)
    if args.json_output:
        out_json = os.path.expanduser(args.json_output)
    else:
        out_json = args.output.replace("_report.md", "_sync.json")

    if args.skip_step1:
        projects = step1_load_cache(args.months)
        if not projects:
            projects, cutoff = step1_fetch_all(args.months)
        else:
            log(f"Step 1: 从缓存加载 {len(projects)} 个项目")
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=args.months * 30)
            cutoff = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        projects, cutoff = step1_fetch_all(args.months)

    if args.skip_step2:
        cache = CACHE_DIR / "gitlab_lfs_candidates.json"
        if cache.exists():
            with open(cache) as f:
                lfs_cands = json.load(f)
            log(f"Step 2: 从缓存加载 {len(lfs_cands)} 个 LFS 项目")
        else:
            lfs_cands = step2_filter_lfs(projects, args.jobs)
    else:
        lfs_cands = step2_filter_lfs(projects, args.jobs)

    if args.list_only or not lfs_cands:
        if args.list_only:
            log(f"列出模式: {len(lfs_cands)} 个 LFS 项目")
            for idx, p in enumerate(lfs_cands, 1):
                ns = p.get("namespace", {}).get("full_path", "")
                print(f"{idx:>4}  {p.get('created_at','')[:10]}  {ns}/{p['name']}")
        return

    if args.max and len(lfs_cands) > args.max:
        log(f"限制前 {args.max} 个项目 (原 {len(lfs_cands)})")
        lfs_cands = lfs_cands[:args.max]

    step3_check_lfs(lfs_cands, args.clusters, args.jobs,
                    cutoff=cutoff, months=args.months,
                    out_md=args.output, out_json=out_json)


if __name__ == "__main__":
    main()
