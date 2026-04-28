#!/usr/bin/env python3
"""Conservative cleanup for Codex, Claude, and Opencode local state."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DAY = 24 * 60 * 60
HOME = Path.home()


@dataclass(frozen=True)
class CleanupRule:
    product: str
    description: str
    paths: tuple[Path, ...]
    mode: str
    max_age_days: int
    keep_recent: int = 0
    enabled: bool = True


@dataclass
class CleanupAction:
    product: str
    path: Path
    description: str
    size_bytes: int
    age_days: float


def path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for name in files:
            file_path = Path(root, name)
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
        for name in dirs:
            dir_path = Path(root, name)
            if dir_path.is_symlink():
                try:
                    total += dir_path.stat().st_size
                except OSError:
                    continue
    return total


def age_days(path: Path, now: float) -> float:
    try:
        return max((now - path.stat().st_mtime) / DAY, 0.0)
    except OSError:
        return 0.0


def iter_children(parent: Path, mode: str) -> list[Path]:
    if not parent.exists():
        return []
    children: list[Path] = []
    if mode == "codex_session_days":
        for year_dir in parent.iterdir():
            if not year_dir.is_dir():
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                for day_dir in month_dir.iterdir():
                    if day_dir.is_dir():
                        children.append(day_dir)
        return children
    for child in parent.iterdir():
        if mode == "files" and child.is_file():
            children.append(child)
        elif mode == "dirs" and child.is_dir():
            children.append(child)
        elif mode == "claude_project_dirs" and child.is_dir() and child.name != "memory":
            children.append(child)
        elif mode == "all":
            children.append(child)
    return children


def keep_newest(items: Iterable[Path], keep_recent: int) -> set[Path]:
    if keep_recent <= 0:
        return set()
    ordered = sorted(
        items,
        key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
        reverse=True,
    )
    return set(ordered[:keep_recent])


def build_rules() -> list[CleanupRule]:
    claude_projects = HOME / ".claude" / "projects"
    claude_project_roots = tuple(
        path
        for path in claude_projects.iterdir()
        if path.is_dir() and path.name != "memory"
    ) if claude_projects.exists() else ()

    project_jsonl_paths = tuple(claude_project_roots)
    project_session_dirs = tuple(claude_project_roots)

    return [
        CleanupRule(
            product="codex",
            description="old session transcripts",
            paths=(HOME / ".codex" / "sessions",),
            mode="codex_session_days",
            max_age_days=14,
            keep_recent=7,
        ),
        CleanupRule(
            product="codex",
            description="old shell snapshots",
            paths=(HOME / ".codex" / "shell_snapshots",),
            mode="files",
            max_age_days=14,
            keep_recent=20,
        ),
        CleanupRule(
            product="codex",
            description="temporary plugin marketplace cache",
            paths=(HOME / ".codex" / ".tmp", HOME / ".codex" / "tmp"),
            mode="all",
            max_age_days=3,
        ),
        CleanupRule(
            product="codex",
            description="ambient suggestion cache",
            paths=(HOME / ".codex" / "ambient-suggestions",),
            mode="all",
            max_age_days=30,
            keep_recent=3,
        ),
        CleanupRule(
            product="claude",
            description="project session transcripts",
            paths=project_jsonl_paths,
            mode="files",
            max_age_days=14,
            keep_recent=10,
        ),
        CleanupRule(
            product="claude",
            description="project tool-results and subagents",
            paths=project_session_dirs,
            mode="claude_project_dirs",
            max_age_days=14,
            keep_recent=10,
        ),
        CleanupRule(
            product="claude",
            description="session environment snapshots",
            paths=(HOME / ".claude" / "session-env",),
            mode="dirs",
            max_age_days=7,
            keep_recent=10,
        ),
        CleanupRule(
            product="claude",
            description="file history cache",
            paths=(HOME / ".claude" / "file-history",),
            mode="dirs",
            max_age_days=14,
            keep_recent=10,
        ),
        CleanupRule(
            product="claude",
            description="paste cache",
            paths=(HOME / ".claude" / "paste-cache",),
            mode="files",
            max_age_days=14,
            keep_recent=10,
        ),
        CleanupRule(
            product="claude",
            description="failed telemetry events",
            paths=(HOME / ".claude" / "telemetry",),
            mode="files",
            max_age_days=30,
            keep_recent=5,
        ),
        CleanupRule(
            product="claude",
            description="downloaded artifacts",
            paths=(HOME / ".claude" / "downloads",),
            mode="all",
            max_age_days=7,
            keep_recent=3,
        ),
        CleanupRule(
            product="opencode",
            description="temporary runtime files",
            paths=(
                HOME / ".opencode" / "tmp",
                HOME / ".opencode" / "cache",
                HOME / ".opencode" / "logs",
                HOME / ".opencode" / "sessions",
                HOME / ".config" / "opencode" / "tmp",
                HOME / ".config" / "opencode" / "cache",
                HOME / ".config" / "opencode" / "logs",
                HOME / ".config" / "opencode" / "sessions",
            ),
            mode="all",
            max_age_days=7,
            keep_recent=3,
        ),
    ]


def collect_actions(products: set[str], now: float) -> list[CleanupAction]:
    actions: list[CleanupAction] = []
    for rule in build_rules():
        if rule.product not in products or not rule.enabled:
            continue
        for parent in rule.paths:
            children = iter_children(parent, rule.mode)
            if not children:
                continue
            protected = keep_newest(children, rule.keep_recent)
            for child in children:
                if child in protected:
                    continue
                item_age = age_days(child, now)
                if item_age < rule.max_age_days:
                    continue
                actions.append(
                    CleanupAction(
                        product=rule.product,
                        path=child,
                        description=rule.description,
                        size_bytes=path_size(child),
                        age_days=item_age,
                    )
                )
    actions.sort(key=lambda action: (action.product, str(action.path)))
    return actions


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        shutil.rmtree(path)


def format_bytes(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)}{unit}"
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{size}B"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean old transient state for Codex, Claude, and Opencode. "
            "Defaults to dry-run."
        )
    )
    parser.add_argument(
        "--products",
        nargs="+",
        choices=("codex", "claude", "opencode"),
        default=("codex", "claude", "opencode"),
        help="Products to scan. Default: all.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete matched files. Default is dry-run.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show every matched path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = set(args.products)
    actions = collect_actions(products=selected, now=time.time())

    if not actions:
        print("No cleanup candidates found.")
        return 0

    total_size = sum(action.size_bytes for action in actions)
    grouped: dict[str, list[CleanupAction]] = {}
    for action in actions:
        grouped.setdefault(action.product, []).append(action)

    mode = "apply" if args.apply else "dry-run"
    print(f"Mode: {mode}")
    print(f"Candidates: {len(actions)}")
    print(f"Reclaimable: {format_bytes(total_size)}")

    for product in sorted(grouped):
        product_actions = grouped[product]
        product_size = sum(action.size_bytes for action in product_actions)
        print(
            f"{product}: {len(product_actions)} paths, "
            f"{format_bytes(product_size)}"
        )
        if args.verbose:
            for action in product_actions:
                print(
                    f"  {action.path} | {action.description} | "
                    f"{action.age_days:.1f}d | {format_bytes(action.size_bytes)}"
                )

    if not args.apply:
        print("Dry-run only. Re-run with --apply to delete these paths.")
        return 0

    failures = 0
    for action in actions:
        try:
            remove_path(action.path)
        except OSError as exc:
            failures += 1
            print(f"Failed to remove {action.path}: {exc}", file=sys.stderr)

    if failures:
        print(f"Cleanup completed with {failures} failures.", file=sys.stderr)
        return 1

    print("Cleanup completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
