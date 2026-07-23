#!/usr/bin/env python3
"""GitLab LFS 多集群完备性扫描器（standalone）

功能：
  1. 扫描最近 N 个月（默认 6 个月）的 GitLab LFS 项目的指针 (OID)，固化到 index JSON
  2. 检查各 MinIO 集群是否存在这些 OID（增量模式：上次已 COMPLETE 的项目自动跳过）
  3. 输出：
     - MD 报告（标题固定为「模型完备性报告」）
     - JSON（按集群列出缺失 OID + 各项目检查状态 check_results）
  4. 可选上传固定标题的飞书文档

固化机制：
  - 默认读取 ~/agent/logs/gitlab_lfs_index.json（上次扫描的项目+指针快照）
  - 只跑 Step 4（mc stat）检查各集群完备性
  - 用 --refresh 重新跑 Step 1-3 刷新 index

增量检查（跳过已 COMPLETE）：
  - 非 --refresh 模式下，自动读取上次 sync JSON 中的 check_results
  - 上次检查为 COMPLETE 的项目，其所有 OID 视为已在各集群中存在，跳过 mc stat
  - INCOMPLETE / 新项目照常检查；--refresh 时重新完整检查

并发策略：
  - Step 4: 单全局线程池，总 worker 上限 32，含重试避免误报

飞书标题固定为「模型完备性报告」，overwrite 时 MD 内容以 `# 模型完备性报告` 开头。

默认输出路径：
  - Index:   ~/agent/logs/gitlab_lfs_index.json   (项目 + LFS 指针快照)
  - Report:  ~/agent/reports/scan_lfs_report.md
  - Sync:    ~/agent/logs/scan_lfs_sync.json

用法:
  python3 ~/agent/scripts/scan_lfs.py                 # 默认：用已有 index + 检查
  python3 ~/agent/scripts/scan_lfs.py --refresh       # 刷新 index + 检查
  python3 ~/agent/scripts/scan_lfs.py --refresh -m 6  # 刷新最近 6 个月（默认）
  python3 ~/agent/scripts/scan_lfs.py --refresh -m 1  # 只扫最近 1 个月
  python3 ~/agent/scripts/scan_lfs.py --refresh --lark  # 刷新 + 上传飞书
  python3 ~/agent/scripts/scan_lfs.py -c xa ks         # 只查部分集群
  python3 ~/agent/scripts/scan_lfs.py --max 10         # 只检查前 10 个项目
  python3 ~/agent/scripts/scan_lfs.py --list-only      # 仅列项目
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

# ======================== 配置 ========================

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

NS_WHITELIST = {"model", "dataset"}
NS_BLACKLIST = {"skills"}

AGENT_DIR = Path(os.path.expanduser("~/agent"))
REPORTS_DIR = AGENT_DIR / "reports"
LOGS_DIR = AGENT_DIR / "logs"

DEFAULT_INDEX = str(LOGS_DIR / "gitlab_lfs_index.json")
DEFAULT_REPORT = str(REPORTS_DIR / "scan_lfs_report.md")
DEFAULT_JSON = str(LOGS_DIR / "scan_lfs_sync.json")
LARK_URL_FILE = str(LOGS_DIR / "lark_doc_url.txt")

FEISHU_DOC_TITLE = "模型完备性报告"


# ======================== 工具函数 ========================

def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str):
    print(f"[{ts()}] {msg}", flush=True)


def oid_path(oid: str, alias: str) -> str:
    return f"{alias}/{BUCKET}/{oid[0:2]}/{oid[2:4]}/{oid[4:]}"


def has_lfs_ext(p: str) -> bool:
    name = p.lower()
    if ".tar." in name:
        return True
    _, ext = os.path.splitext(name)
    return ext in LFS_EXTENSIONS


# ======================== Index 管理 ========================

def load_index(path: str):
    p = Path(path)
    if not p.exists():
        log(f"Index 不存在: {path}")
        return None
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    log(f"Index 加载: {path} (refresh_time={data.get('refresh_time','?')}, "
        f"projects={len(data.get('projects', {}))})")
    return data


def save_index(data: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log(f"Index 保存: {path} (projects={len(data.get('projects', {}))})")


# ======================== Index 刷新：Step 1-3 ========================

def fetch_page_curl(page: int, after: str, per_page: int = 100):
    out_path = Path(f"/tmp/gitlab_page_{page}.json")
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


def step1_fetch_all(months: int, jobs: int = 20) -> tuple:
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    cutoff_date = cutoff.strftime("%Y-%m-%d")

    log(f"Step 1: 下载最近 {months} 个月项目 (created_after={cutoff_date})")

    projects = []
    page = 1
    max_page = 400

    while page <= max_page:
        batch_size = min(jobs, max_page - page + 1)
        pages = list(range(page, page + batch_size))
        results = {}

        with ThreadPoolExecutor(max_workers=jobs) as pool:
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
            (Path(f"/tmp/gitlab_page_{p}.json")).unlink(missing_ok=True)

        if all_empty:
            log(f"  page {page} 空，停止")
            break

        log(f"  已获取 {len(projects)} 个项目 (page={pages[-1]})")
        page = pages[-1] + 1

    log(f"Step 1 完成: {len(projects)} 个项目")
    return projects, after


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


def step2_filter_lfs(projects: list, jobs: int = 16) -> list:
    ns_match, skipped, other = [], 0, []
    for p in projects:
        top_ns = p.get("namespace", {}).get("full_path", "").split("/")[0]
        if top_ns in NS_WHITELIST:
            ns_match.append(p)
        elif top_ns in NS_BLACKLIST:
            skipped += 1
        else:
            other.append(p)

    log(f"Step 2: ns 命中 {len(ns_match)} (whitelist={NS_WHITELIST}), "
        f"跳过 {skipped} (blacklist={NS_BLACKLIST}), API 检查 {len(other)}")

    lfs_cands = list(ns_match)
    done = 0
    if other:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futs = {pool.submit(check_gitattributes, p): p for p in other}
            for fut in as_completed(futs):
                done += 1
                try:
                    if fut.result():
                        lfs_cands.append(futs[fut])
                except Exception:
                    pass
                if done % 200 == 0 or done == len(other):
                    log(f"  进度 {done}/{len(other)}  LFS候选={len(lfs_cands)}")

    lfs_cands.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    log(f"Step 2 完成: {len(lfs_cands)} 个 LFS 候选项目")
    return lfs_cands


def fetch_lfs_pointers_via_api(project: dict, max_files: int = 5000):
    """通过 GitLab API 获取 LFS 指针（不需要 git clone）"""
    pid = project["id"]
    ref = project.get("default_branch") or "main"
    pointers = []

    try:
        r = subprocess.run(
            [
                "curl", "-sk", "--max-time", "30",
                "-u", f"{GITLAB_USER}:{GITLAB_PASS}",
                f"{GITLAB_URL}/api/v4/projects/{pid}/repository/tree?ref={ref}&recursive=true&per_page=100",
            ],
            capture_output=True, timeout=40, text=True,
        )
        if r.returncode != 0 or not r.stdout:
            return project, []

        tree = json.loads(r.stdout)
        if not isinstance(tree, list):
            return project, []

        lfs_files = [item["path"] for item in tree
                     if item.get("type") == "blob" and has_lfs_ext(item["path"])]

        if len(lfs_files) > max_files:
            lfs_files = lfs_files[:max_files]

        for path in lfs_files:
            try:
                req = subprocess.run(
                    [
                        "curl", "-sk", "--max-time", "15",
                        "-u", f"{GITLAB_USER}:{GITLAB_PASS}",
                        f"{GITLAB_URL}/api/v4/projects/{pid}/repository/files/{quote(path, safe='')}/raw?ref={ref}",
                    ],
                    capture_output=True, timeout=20, text=True,
                )
                if req.returncode == 0 and req.stdout:
                    m = LFS_POINTER_RE.match(req.stdout)
                    if m:
                        pointers.append({
                            "file": path,
                            "oid": m.group(1),
                            "size": int(m.group(2)),
                        })
            except Exception:
                continue

    except Exception:
        return project, []

    return project, pointers


def step3_fetch_pointers(lfs_projects: list, workers: int = 8) -> dict:
    """并发获取每个项目的 LFS 指针列表，返回 {project_path: pointers_list}"""
    log(f"Step 3: Fetch LFS pointers via API (workers={workers}, 项目={len(lfs_projects)})...")
    project_pointers = {}
    done_fetch = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fetch_lfs_pointers_via_api, p): p for p in lfs_projects}
        for fut in as_completed(futs):
            p, pointers = fut.result()
            done_fetch += 1
            ns = p.get("namespace", {}).get("full_path", "")
            full_name = f"{ns}/{p['name']}"
            project_pointers[full_name] = {
                "created": p.get("created_at", "")[:10],
                "pointers": pointers,
            }
            if done_fetch % 50 == 0 or done_fetch == len(lfs_projects):
                n_with = sum(1 for v in project_pointers.values() if v["pointers"])
                log(f"  fetch 进度 {done_fetch}/{len(lfs_projects)}  有LFS指针={n_with}")
    return project_pointers


def refresh_index(months: int, jobs: int = 16, index_path: str = DEFAULT_INDEX) -> dict:
    """刷新 index：跑 Step 1 + Step 2 + Step 3"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    projects, _ = step1_fetch_all(months, min(jobs * 2, 20))
    lfs_cands = step2_filter_lfs(projects, jobs)
    project_data = step3_fetch_pointers(lfs_cands, workers=min(jobs, 8))

    index = {
        "refresh_time": datetime.now().isoformat(),
        "months": months,
        "cutoff": after,
        "total_projects": len(projects),
        "lfs_projects": len(lfs_cands),
        "projects": project_data,
    }
    save_index(index, index_path)
    return index


# ======================== 增量检查：加载上次结果 ========================

def load_prev_sync(path: str = DEFAULT_JSON) -> dict:
    """加载上次 sync JSON 中各项目的检查状态，用于跳过已 COMPLETE 的项目。"""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("check_results", {})
    except Exception:
        return {}


# ======================== Step 4: mc stat ========================

def check_oid_in_cluster(oid: str, cluster: str, retries: int = 2):
    """单个 (oid, cluster) 的 mc stat 调用，含重试"""
    for attempt in range(retries + 1):
        try:
            r = subprocess.run(
                [MC, "stat", oid_path(oid, cluster)],
                capture_output=True, timeout=30,
            )
            if r.returncode == 0:
                return oid, cluster, True
            if attempt < retries:
                time.sleep(0.2 * (attempt + 1))
                continue
            return oid, cluster, False
        except subprocess.TimeoutExpired:
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
            else:
                return oid, cluster, False


def step4_check_clusters(project_pointers: dict, clusters: list,
                          jobs_per_cluster: int = 16,
                          skipped_projects: frozenset | None = None) -> dict:
    """检查所有 OID 在各集群的存在情况。
    project_pointers: {proj_path: [ptr_dict, ...]}
    已经标记为 COMPLETE 的项目 (skipped_projects) 不需要再次 mc stat,
    直接视为所有集群已存在。
    """
    skipped_projects = skipped_projects or frozenset()
    max_total_workers = 32
    total_workers = min(jobs_per_cluster * len(clusters), max_total_workers)

    all_jobs = set()
    for proj_path, pointers in project_pointers.items():
        for ptr in pointers:
            for c in clusters:
                all_jobs.add((ptr["oid"], c))

    results: dict[tuple[str, str], bool] = {}

    if skipped_projects:
        n_skip = 0
        for proj_path in list(skipped_projects):
            if proj_path in project_pointers:
                for ptr in project_pointers[proj_path]:
                    for c in clusters:
                        results[(ptr["oid"], c)] = True
                        n_skip += 1
        all_jobs -= set(results.keys())
        log(f"  跳过已 COMPLETE 的项目: {len(skipped_projects)} 个项目, "
            f"{n_skip} 个 OID x 集群任务")

    total_oids = len(set(j[0] for j in all_jobs))
    log(f"Step 4: mc stat {total_oids} OID x {len(clusters)} 集群 "
        f"(总任务 {len(all_jobs)}, 并发 worker={total_workers})")

    if not all_jobs:
        return results

    with ThreadPoolExecutor(max_workers=total_workers) as pool:
        futs = {
            pool.submit(check_oid_in_cluster, oid, c): (oid, c)
            for oid, c in all_jobs
        }
        done = 0
        for fut in as_completed(futs):
            oid, cluster, exists = fut.result()
            results[(oid, cluster)] = exists
            done += 1
            if done % 500 == 0 or done == len(all_jobs):
                log(f"  mc stat 进度 {done}/{len(all_jobs)}")

    return results


# ======================== 报告生成 ========================

def generate_reports(cluster_results: dict, projects_slice: list,
                     clusters: list, cutoff_iso: str, months: int,
                     out_md: str, out_json: str,
                     skipped_projects: frozenset | None = None,
                     prev_check_results: dict | None = None):
    """汇总各项目结果，生成 MD + JSON
    projects_slice: [(proj_path, pdata), ...] where pdata 有 'created' 和 'pointers'
    上次已 COMPLETE 的项目 (skipped_projects) 直接使用 prev_check_results 中的结果,
    不再重新检查。
    """
    skipped_projects = skipped_projects or frozenset()
    prev_check_results = prev_check_results or {}

    check_results: dict[str, dict] = {}
    scan_time_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []
    for proj_path, pdata in projects_slice:
        pointers = pdata.get("pointers", [])
        if not pointers:
            results.append({
                "project": proj_path,
                "created": pdata.get("created", ""),
                "lfs_count": 0,
                "status": "无LFS对象",
                "cluster_stats": {c: {"miss": 0} for c in clusters},
                "missing_items": [],
            })
            continue

        cluster_stats = {c: {"total": 0, "exist": 0, "miss": 0} for c in clusters}
        missing_items = []

        for ptr in pointers:
            oid = ptr["oid"]
            for c in clusters:
                cluster_stats[c]["total"] += 1
                if cluster_results.get((oid, c)):
                    cluster_stats[c]["exist"] += 1
                else:
                    cluster_stats[c]["miss"] += 1
            miss_clusters = [c for c in clusters if not cluster_results.get((oid, c))]
            if miss_clusters:
                missing_items.append({
                    "oid": oid, "file": ptr["file"],
                    "missing_in": miss_clusters,
                })

        all_ok = all(cluster_stats[c]["miss"] == 0 for c in clusters)
        status = "COMPLETE" if all_ok else "INCOMPLETE"
        results.append({
            "project": proj_path,
            "created": pdata.get("created", ""),
            "lfs_count": len(pointers),
            "status": status,
            "cluster_stats": cluster_stats,
            "missing_items": missing_items,
            "missing_count": len(missing_items),
        })
        skipped = proj_path in skipped_projects
        check_results[proj_path] = {
            "status": status,
            "last_checked": prev_check_results.get(proj_path, {}).get("last_checked") if skipped else scan_time_iso,
            "skip": skipped,
        }

    # --- MD 报告 ---
    with_lfs = [r for r in results if r['lfs_count'] > 0]
    no_lfs = [r for r in results if r['lfs_count'] == 0]
    incomplete = [r for r in with_lfs if r['status'] == 'INCOMPLETE']
    complete = [r for r in with_lfs if r['status'] == 'COMPLETE']
    scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = [
        f"# {FEISHU_DOC_TITLE}",
        "",
        f"- 扫描时间: {scan_time}",
        f"- 时间范围: {cutoff_iso[:10]} ~ 今 (最近 {months} 个月)",
        f"- 集群: {', '.join(clusters)}",
        f"- 有 LFS 对象: {len(with_lfs)} (完整 {len(complete)}, **不完整 {len(incomplete)}**)",
        f"- 无 LFS 对象: {len(no_lfs)}",
        "",
        "## 集群缺失情况",
        "",
        "| 集群 | 完备 | 缺失 | 缺失率 |",
        "|------|------|------|--------|",
    ]
    for c in clusters:
        miss = len([r for r in with_lfs if r['cluster_stats'][c]['miss'] > 0])
        ok = len(with_lfs) - miss
        rate = f'{miss / len(with_lfs) * 100:.1f}%' if len(with_lfs) > 0 and miss > 0 else '0%'
        md.append(f'| {c} | {ok} | {miss} | {rate} |')

    if incomplete:
        md.extend([
            "",
            f"## 不完整项目列表 ({len(incomplete)} 个)",
            "",
            "| 项目 | 社区 | 创建时间 | LFS数 | " + " | ".join(clusters) + " |",
            "|" + "---|" * (4 + len(clusters)),
        ])
        for r in incomplete:
            proj = r['project']
            gitlab_url = f"{GITLAB_URL}/{proj}"
            community_url = proj.replace("model/", "", 1)
            community_path = f"https://www.scnet.cn/ui/aihub/models/{community_url}"

            gitlab_col = f"[{proj}]({gitlab_url})"
            community_col = f"[社区]({community_path})"

            marks = []
            for c in clusters:
                marks.append("❌" if r['cluster_stats'][c]['miss'] > 0 else "✅")
            md.append(f"| {gitlab_col} | {community_col} | {r['created']} | {r['lfs_count']} | " +
                      " | ".join(marks) + " |")

    if complete:
        md.extend([
            "",
            f"## 完整项目列表 ({len(complete)} 个)",
            "",
            "| 项目 | 社区 | 创建时间 | LFS数 | " + " | ".join(clusters) + " |",
            "|" + "---|" * (4 + len(clusters)),
        ])
        for r in complete:
            proj = r['project']
            gitlab_url = f"{GITLAB_URL}/{proj}"
            community_url = proj.replace("model/", "", 1)
            community_path = f"https://www.scnet.cn/ui/aihub/models/{community_url}"

            gitlab_col = f"[{proj}]({gitlab_url})"
            community_col = f"[社区]({community_path})"
            marks = ["✅" for _ in clusters]
            md.append(f"| {gitlab_col} | {community_col} | {r['created']} | {r['lfs_count']} | " +
                      " | ".join(marks) + " |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    # --- JSON 同步计划 ---
    sync_plan = {c: {} for c in clusters}
    for r in results:
        for item in r.get('missing_items', []):
            for c in item['missing_in']:
                oid = item['oid']
                if oid not in sync_plan[c]:
                    sync_plan[c][oid] = {
                        "oid": oid,
                        "file": item['file'],
                        "projects": [],
                    }
                if r['project'] not in sync_plan[c][oid]['projects']:
                    sync_plan[c][oid]['projects'].append(r['project'])

    n_skipped = sum(1 for v in check_results.values() if v.get("skip"))
    n_checked = sum(1 for v in check_results.values() if not v.get("skip"))

    json_out = {
        "_summary": {
            "scan_time": scan_time,
            "cutoff": cutoff_iso,
            "months": months,
            "total_lfs_projects": len(with_lfs),
            "incomplete_projects": len(incomplete),
            "skipped_projects": n_skipped,
            "checked_projects": n_checked,
        },
        "check_results": {
            proj: check_results[proj] for proj in (
                sorted(proj for proj in check_results if check_results[proj]["status"] == "INCOMPLETE")
                + sorted(proj for proj in check_results if check_results[proj]["status"] == "COMPLETE")
            )
        },
    }
    for c in clusters:
        json_out[c] = {
            "missing_count": len(sync_plan[c]),
            "oids": sync_plan[c],
        }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(json_out, f, indent=2, ensure_ascii=False)

    log("")
    log("✅ 完成")
    log(f"   MD:   {out_md}")
    log(f"   JSON: {out_json}")
    log("")
    log(f"   跳过已 COMPLETE: {n_skipped} 个项目, 实际检查: {n_checked} 个项目")
    for c in clusters:
        n = len(sync_plan[c])
        if n > 0:
            log(f"   {c}: {n} OID 待同步")
        else:
            log(f"   {c}: 完备")


# ======================== 飞书上传 ========================

def get_lark_url() -> str:
    p = Path(LARK_URL_FILE)
    return p.read_text().strip() if p.exists() else ""


def save_lark_url(url: str):
    os.makedirs(os.path.dirname(LARK_URL_FILE), exist_ok=True)
    Path(LARK_URL_FILE).write_text(url.strip())


def split_lark_markdown(content: str, max_table_rows: int = 50) -> list[str]:
    """将 Markdown 拆成适合飞书批量写入的小块，大表分批并重复表头。"""
    lines = content.splitlines()
    chunks = []
    pending = []
    i = 0

    def flush_pending():
        if pending and any(line.strip() for line in pending):
            chunks.append("\n".join(pending).strip() + "\n")
        pending.clear()

    while i < len(lines):
        if (
            lines[i].startswith("|")
            and i + 1 < len(lines)
            and lines[i + 1].startswith("|")
        ):
            flush_pending()
            header = lines[i:i + 2]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            for start in range(0, len(rows), max_table_rows):
                batch = header + rows[start:start + max_table_rows]
                chunks.append("\n".join(batch) + "\n")
        else:
            pending.append(lines[i])
            i += 1

    flush_pending()
    return chunks


def run_lark_write(cmd: list[str], content: str, env: dict) -> dict:
    r = subprocess.run(
        cmd, input=content.encode(), capture_output=True, timeout=120, env=env,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="ignore")[:500])
    try:
        response = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"飞书返回非 JSON: {r.stdout.decode(errors='ignore')[:500]}") from e
    if not response.get("ok"):
        raise RuntimeError(f"飞书写入失败: {response}")
    data = response.get("data", {})
    if data.get("result") not in (None, "success") or data.get("warnings"):
        raise RuntimeError(
            f"飞书写入未完全成功: result={data.get('result')}, "
            f"warnings={data.get('warnings')}"
        )
    return response


def upload_to_lark(out_md: str):
    """用 lark-cli 创建/更新飞书文档，标题固定为 FEISHU_DOC_TITLE"""
    url = get_lark_url()

    log("上传飞书...")
    try:
        with open(out_md, encoding="utf-8") as f:
            content = f.read()

        chunks = split_lark_markdown(content)
        if not chunks:
            raise RuntimeError("报告内容为空")

        cmd = ["lark-cli", "docs"]
        if url:
            cmd.extend([
                "+update", "--doc", url,
                "--command", "overwrite",
            ])
        else:
            cmd.extend([
                "+create",
                "--title", FEISHU_DOC_TITLE,
            ])
        cmd.extend(["--doc-format", "markdown", "--content", "-"])

        env = os.environ.copy()
        env["LARKSUITE_CLI_NO_UPDATE_NOTIFIER"] = "1"
        env["LARKSUITE_CLI_NO_SKILLS_NOTIFIER"] = "1"

        response = run_lark_write(cmd, chunks[0], env)
        new_url = response.get("data", {}).get("document", {}).get("url")
        if new_url:
            url = new_url
            save_lark_url(new_url)

        for idx, chunk in enumerate(chunks[1:], 2):
            append_cmd = [
                "lark-cli", "docs", "+update", "--doc", url,
                "--command", "append", "--doc-format", "markdown",
                "--content", "-",
            ]
            run_lark_write(append_cmd, chunk, env)
            log(f"  飞书分段写入 {idx}/{len(chunks)}")

        log(f"飞书文档: {url}")
    except Exception as e:
        log(f"飞书上传异常: {e}")


# ======================== 主函数 ========================

def main():
    example = """
使用示例:
  %(prog)s                          默认行为: 复用已有 index, 检查各集群 MinIO 完备性, 上传飞书
  %(prog)s --no-lark                同上, 但不上传飞书
  %(prog)s --refresh                刷新 index (重新获取 GitLab 项目 + LFS 指针) + 检查 + 上传飞书
  %(prog)s --refresh -m 1           只刷新最近 1 个月的项目
  %(prog)s -c xa qd                 只检查 xa 和 qd 两个集群 (仍上传飞书)
  %(prog)s --max 20                 只检查前 20 个项目 (快速验证)
  %(prog)s --list-only              仅列出项目, 不执行 mc stat 检查
  %(prog)s -j 16                    提高每个集群并发 (默认 8, 总并发上限 32)

输出文件 (默认):
  ~/agent/logs/gitlab_lfs_index.json    index (GitLab 项目 + LFS 指针快照, 长期固化)
  ~/agent/logs/scan_lfs_sync.json       同步计划 (按集群列出缺失 OID + 引用项目)
  ~/agent/logs/lark_doc_url.txt         飞书文档 URL (自动创建/复用)
  ~/agent/reports/scan_lfs_report.md    报告 (标题固定为「模型完备性报告」)

典型工作流:
  1. 日常巡检 (复用 index, 上传飞书):  python3 ~/agent/scripts/scan_lfs.py
  2. 项目列表变更后 (刷新 index):      python3 ~/agent/scripts/scan_lfs.py --refresh
  3. 只看部分集群:                     python3 ~/agent/scripts/scan_lfs.py -c xa qd
  4. 不上传飞书:                       python3 ~/agent/scripts/scan_lfs.py --no-lark
"""
    parser = argparse.ArgumentParser(
        description="GitLab LFS 多集群完备性扫描器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=example,
    )
    parser.add_argument("--refresh", action="store_true",
                        help="重新跑 Step 1-3 刷新 index (GitLab 项目 + LFS 指针); "
                             "不加则复用已有 index, 只跑 Step 4 (mc stat)")
    parser.add_argument("-m", "--months", type=int, default=6,
                        help="刷新 index 时扫描最近 N 个月 (默认 6, 仅在 --refresh 时生效)")
    parser.add_argument("-c", "--clusters", nargs="+", default=DEFAULT_CLUSTERS,
                        help=f"MinIO 集群别名列表 (默认: {' '.join(DEFAULT_CLUSTERS)})")
    parser.add_argument("-j", "--jobs", type=int, default=8,
                        help="每个集群并发 jobs (默认 8, 总并发上限 32)")
    parser.add_argument("--list-only", action="store_true",
                        help="仅列出项目, 不执行 mc stat 检查")
    parser.add_argument("--max", type=int, default=0,
                        help="限制最多检查的项目数 (默认 0=全部, 用于快速验证)")
    parser.add_argument("--index", default=DEFAULT_INDEX,
                        help=f"index 文件路径 (默认: {DEFAULT_INDEX})")
    parser.add_argument("-o", "--output", default=DEFAULT_REPORT,
                        help=f"MD 报告输出路径 (默认: {DEFAULT_REPORT})")
    parser.add_argument("--json-output", default=DEFAULT_JSON,
                        help=f"同步计划 JSON 输出路径 (默认: {DEFAULT_JSON})")
    parser.add_argument("--lark", action="store_true", default=True,
                        help="完成后上传飞书 (标题固定: 模型完备性报告, URL 自动复用; 默认开启)")
    parser.add_argument("--no-lark", action="store_true", dest="no_lark",
                        help="不上传飞书")
    args = parser.parse_args()

    args.output = os.path.expanduser(args.output)
    args.json_output = os.path.expanduser(args.json_output)
    args.index = os.path.expanduser(args.index)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(os.path.dirname(args.json_output), exist_ok=True)
    os.makedirs(os.path.dirname(args.index), exist_ok=True)

    # --- Index: 加载或刷新 ---
    if args.refresh:
        log("模式: --refresh 刷新 Index")
        index = refresh_index(args.months, args.jobs, args.index)
    else:
        index = load_index(args.index)
        if not index:
            log("无 Index，自动进入 --refresh 模式")
            index = refresh_index(args.months, args.jobs, args.index)

    cutoff_iso = index.get("cutoff", "")
    months = index.get("months", args.months)

    prev_check = {} if args.refresh else load_prev_sync(args.json_output)

    # 选取要检查的项目集合
    items = list(index["projects"].items())
    if args.max and len(items) > args.max:
        log(f"限制前 {args.max} 个项目 (原 {len(items)})")
        items = items[:args.max]

    if args.list_only:
        log(f"列出模式: {len(items)} 个项目")
        for idx, (proj, pdata) in enumerate(items, 1):
            n = len(pdata.get("pointers", []))
            print(f"{idx:>4}  {pdata.get('created', ''):10}  LFS={n:<4}  {proj}")
        return

    # --- 标记上次已 COMPLETE 的项目为跳过 ---
    current_items = {proj for proj, _ in items}
    skipped_projects = frozenset(
        proj for proj, r in prev_check.items()
        if r.get("status") == "COMPLETE" and proj in current_items
    )
    if skipped_projects:
        log(f"从上次检查结果中复用: {len(skipped_projects)} 个已 COMPLETE 项目将跳过 mc stat")

    # --- Step 4: mc stat ---
    project_pointers = {p: pdata.get("pointers", []) for p, pdata in items}
    cluster_results = step4_check_clusters(
        project_pointers, args.clusters, args.jobs,
        skipped_projects=skipped_projects,
    )

    # --- 生成报告 ---
    generate_reports(
        cluster_results, items, args.clusters,
        cutoff_iso, months, args.output, args.json_output,
        skipped_projects=skipped_projects,
        prev_check_results=prev_check,
    )

    # --- 飞书上传 ---
    if args.lark and not args.no_lark:
        upload_to_lark(args.output)


if __name__ == "__main__":
    main()
