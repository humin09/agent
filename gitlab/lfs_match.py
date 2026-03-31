#!/usr/bin/env python3
"""
匹配 GitLab 仓库与本地目录，基于名称语义相似度。

背景：LFS 对象补充上传时，需要将 GitLab 仓库与 xa-login 上的本地
     模型目录对应起来。本脚本从仓库 URL 和目录路径中提取关键字，
     通过语义相似度自动匹配，生成对照表。

规则:
  1. git 仓库: 取最后一个 '/' 到 '.git' 之间的文本，lower case
  2. 文件夹: 取最后一个 '/' 之后的文本，lower case
  3. 两者进行语义相似度匹配，找到最佳匹配
  4. 未匹配上的留空
  5. 输出 markdown 报告

用法:
  # 直接传参
  python3 lfs_match.py -r repos.txt -d dirs.txt

  # 混合传参
  python3 lfs_match.py \
    -r repos.txt \
    --repo https://gitlab.scnet.cn:9002/model/sugon_scnet/DeepSeek-V3.2.git \
    -d dirs.txt \
    --dir /work/home/openaimodels/ai_community/model/Qwen/Qwen3.5-27B

  # 调整阈值（默认 0.4）
  python3 lfs_match.py -r repos.txt -d dirs.txt -t 0.5

  # 输出到文件
  python3 lfs_match.py -r repos.txt -d dirs.txt -o match_report.md
"""

import argparse
import re
import sys
from difflib import SequenceMatcher
from datetime import datetime


def extract_repo_keyword(url: str) -> str:
    """从 git 仓库 URL 提取关键字: 最后一个 '/' 到 '.git' 之间的文本，lower case"""
    url = url.strip().rstrip("/")
    # 去掉 .git 后缀
    if url.endswith(".git"):
        url = url[:-4]
    # 取最后一个 '/' 之后的部分
    keyword = url.rsplit("/", 1)[-1]
    return keyword.lower()


def extract_dir_keyword(path: str) -> str:
    """从文件夹路径提取关键字: 最后一个 '/' 之后的文本，lower case"""
    path = path.strip().rstrip("/")
    keyword = path.rsplit("/", 1)[-1]
    return keyword.lower()


def normalize(s: str) -> str:
    """标准化字符串用于相似度比较: 去除分隔符和版本号格式差异"""
    # 统一分隔符为空格
    s = re.sub(r"[-_.\s]+", " ", s)
    return s.strip()


def semantic_similarity(a: str, b: str) -> float:
    """计算两个关键字的语义相似度 (0~1)"""
    na, nb = normalize(a), normalize(b)

    # 1. 完全匹配
    if na == nb:
        return 1.0

    # 2. 一方包含另一方
    if na in nb or nb in na:
        shorter, longer = sorted([na, nb], key=len)
        return 0.8 + 0.2 * (len(shorter) / len(longer))

    # 3. token 重叠度
    tokens_a = set(na.split())
    tokens_b = set(nb.split())
    if tokens_a and tokens_b:
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        jaccard = len(intersection) / len(union)
    else:
        jaccard = 0.0

    # 4. SequenceMatcher 编辑距离
    seq_ratio = SequenceMatcher(None, na, nb).ratio()

    # 加权综合
    return max(jaccard * 0.9 + seq_ratio * 0.1, seq_ratio)


def read_list_from_file(filepath: str) -> list[str]:
    items = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                items.append(line)
    return items


def match(repos: list[str], dirs: list[str], threshold: float) -> list[dict]:
    """对每个 repo 找到最佳匹配的 dir"""
    repo_kws = [(r, extract_repo_keyword(r)) for r in repos]
    dir_kws = [(d, extract_dir_keyword(d)) for d in dirs]

    matched_dirs = set()
    results = []

    # 计算所有配对的相似度
    all_pairs = []
    for i, (repo, rkw) in enumerate(repo_kws):
        for j, (d, dkw) in enumerate(dir_kws):
            score = semantic_similarity(rkw, dkw)
            all_pairs.append((score, i, j))

    # 按相似度降序，贪心匹配（每个 repo 和 dir 只匹配一次）
    all_pairs.sort(key=lambda x: x[0], reverse=True)
    matched_repos = set()
    matched_dirs = set()
    match_map = {}  # repo_idx -> (dir_idx, score)

    for score, ri, di in all_pairs:
        if ri in matched_repos or di in matched_dirs:
            continue
        if score >= threshold:
            match_map[ri] = (di, score)
            matched_repos.add(ri)
            matched_dirs.add(di)

    # 构建结果
    for i, (repo, rkw) in enumerate(repo_kws):
        entry = {"repo": repo, "repo_keyword": rkw}
        if i in match_map:
            di, score = match_map[i]
            entry["dir"] = dir_kws[di][0]
            entry["dir_keyword"] = dir_kws[di][1]
            entry["score"] = score
        else:
            entry["dir"] = ""
            entry["dir_keyword"] = ""
            entry["score"] = 0.0
        results.append(entry)

    # 未匹配的 dir
    unmatched_dirs = []
    for j, (d, dkw) in enumerate(dir_kws):
        if j not in matched_dirs:
            unmatched_dirs.append({"dir": d, "dir_keyword": dkw})

    return results, unmatched_dirs


def generate_report(results: list[dict], unmatched_dirs: list[dict], threshold: float) -> str:
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"# LFS 仓库-目录匹配报告")
    lines.append(f"")
    lines.append(f"生成时间: {now}  ")
    lines.append(f"匹配阈值: {threshold}")
    lines.append(f"")

    # 匹配结果表
    matched = [r for r in results if r["dir"]]
    unmatched_repos = [r for r in results if not r["dir"]]

    lines.append(f"## 匹配结果 ({len(matched)}/{len(results)})")
    lines.append(f"")
    lines.append(f"| 仓库关键字 | 目录关键字 | 相似度 | 仓库 URL | 目录路径 |")
    lines.append(f"|-----------|-----------|--------|---------|---------|")
    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        repo_kw = r["repo_keyword"]
        dir_kw = r["dir_keyword"] if r["dir_keyword"] else "-"
        score = f"{r['score']:.2f}" if r["score"] > 0 else "-"
        dir_path = r["dir"] if r["dir"] else "-"
        lines.append(f"| {repo_kw} | {dir_kw} | {score} | {r['repo']} | {dir_path} |")
    lines.append(f"")

    # 未匹配的仓库
    if unmatched_repos:
        lines.append(f"## 未匹配的仓库 ({len(unmatched_repos)})")
        lines.append(f"")
        for r in unmatched_repos:
            lines.append(f"- `{r['repo_keyword']}` — {r['repo']}")
        lines.append(f"")

    # 未匹配的目录
    if unmatched_dirs:
        lines.append(f"## 未匹配的目录 ({len(unmatched_dirs)})")
        lines.append(f"")
        for d in unmatched_dirs:
            lines.append(f"- `{d['dir_keyword']}` — {d['dir']}")
        lines.append(f"")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="匹配 GitLab 仓库与本地目录（语义相似度）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--repo", action="append", default=[], help="GitLab 仓库 URL（可多次指定）")
    parser.add_argument("-r", "--repo-file", help="从文件读取仓库 URL 列表")
    parser.add_argument("--dir", action="append", default=[], help="本地目录路径（可多次指定）")
    parser.add_argument("-d", "--dir-file", help="从文件读取目录路径列表")
    parser.add_argument("-t", "--threshold", type=float, default=0.4, help="匹配阈值 (0~1，默认 0.4)")
    parser.add_argument("-o", "--output", help="输出 markdown 文件路径（默认输出到 stdout）")
    args = parser.parse_args()

    repos = list(args.repo)
    if args.repo_file:
        repos.extend(read_list_from_file(args.repo_file))

    dirs = list(args.dir)
    if args.dir_file:
        dirs.extend(read_list_from_file(args.dir_file))

    if not repos:
        print("错误: 至少需要提供一个仓库 URL（--repo 或 -r）", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    if not dirs:
        print("错误: 至少需要提供一个目录路径（--dir 或 -d）", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    results, unmatched_dirs = match(repos, dirs, args.threshold)
    report = generate_report(results, unmatched_dirs, args.threshold)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"报告已输出到: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
