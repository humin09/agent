#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_BUCKET = "gitlab-lfs-prod"
DEFAULT_TIMEOUT_SECONDS = 2 * 60 * 60  # 2h hard ceiling
DEFAULT_IDLE_TIMEOUT_SECONDS = 5 * 60  # kill mc if 0 IO progress for 5min
DEFAULT_WATCHDOG_INTERVAL_SECONDS = 30
DEFAULT_MAX_RETRIES = 5
DEFAULT_SKIP_HOURS = 24
DEFAULT_FAIL_COOLDOWN_MIN = 10
DEFAULT_BACKOFF_BASE = 30
DEFAULT_BACKOFF_MAX = 300


@dataclass
class PrefixResult:
    prefix: str
    status: str
    attempt: int
    message: str


class SyncState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return {}

    def should_skip_success(self, prefix: str, now_ts: float, skip_seconds: int) -> bool:
        item = self.data.get(prefix, {})
        if item.get("last_result") != "success":
            return False
        last_success = item.get("last_success_ts")
        if not isinstance(last_success, (int, float)):
            return False
        return now_ts - last_success < skip_seconds

    def should_skip_failure(
        self, prefix: str, now_ts: float, cooldown_seconds: int, max_retries: int
    ) -> bool:
        item = self.data.get(prefix, {})
        if item.get("last_result") != "failed":
            return False
        if item.get("last_attempt", 0) < max_retries:
            return False
        last_failure = item.get("last_failure_ts")
        if not isinstance(last_failure, (int, float)):
            return False
        return now_ts - last_failure < cooldown_seconds

    def mark_success(self, prefix: str, attempt: int) -> None:
        item = self.data.setdefault(prefix, {})
        item["last_result"] = "success"
        item["last_success_ts"] = time.time()
        item["last_success_at"] = iso_now()
        item["last_attempt"] = attempt
        self._save()

    def mark_failure(self, prefix: str, attempt: int, message: str) -> None:
        item = self.data.setdefault(prefix, {})
        item["last_result"] = "failed"
        item["last_failure_ts"] = time.time()
        item["last_failure_at"] = iso_now()
        item["last_attempt"] = attempt
        item["last_error"] = message
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True))


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_log(log_path: Path, prefix: str, attempt: int, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{iso_now()}] prefix={prefix} attempt={attempt} FAILED {message}\n"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def summarize_message(message: str, max_lines: int = 3) -> str:
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if not lines:
        return "no error output"
    if len(lines) <= max_lines:
        return " | ".join(lines)
    head = " | ".join(lines[:max_lines])
    return f"{head} | ... ({len(lines) - max_lines} more lines)"


def format_duration(seconds: float) -> str:
    total = max(0, int(math.ceil(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _read_proc_io(pid: int) -> int | None:
    """Return rchar+wchar from /proc/<pid>/io; None if unreadable."""
    try:
        with open(f"/proc/{pid}/io") as fh:
            total = 0
            for line in fh:
                if line.startswith(("rchar:", "wchar:")):
                    total += int(line.split()[1])
            return total
    except (FileNotFoundError, PermissionError, ValueError):
        return None


def run_mirror(
    mc_bin: str,
    bucket: str,
    prefix: str,
    timeout_seconds: int,
    idle_timeout_seconds: int,
    watchdog_interval: int,
    limit_upload: str | None,
    limit_download: str | None,
) -> tuple[bool, str]:
    """Run mc mirror with a hard timeout + idle-IO watchdog.

    Hard timeout: kill if total wall time > timeout_seconds.
    Idle watchdog: kill if /proc/<pid>/io rchar+wchar doesn't grow for
        idle_timeout_seconds (distinguishes "stuck" from "slow but progressing").
    """
    src = f"origin/{bucket}/{prefix}/"
    dst = f"local/{bucket}/{prefix}/"
    cmd = [mc_bin, "mirror", "--overwrite", "--preserve"]
    if limit_upload:
        cmd += ["--limit-upload", limit_upload]
    if limit_download:
        cmd += ["--limit-download", limit_download]
    cmd += [src, dst]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ.copy(),
    )

    start = time.time()
    last_io = _read_proc_io(proc.pid) or 0
    last_progress_at = start
    kill_reason: str | None = None

    while True:
        try:
            proc.wait(timeout=watchdog_interval)
            break  # process exited
        except subprocess.TimeoutExpired:
            pass

        now = time.time()
        if now - start > timeout_seconds:
            kill_reason = f"hard timeout after {int(now - start)}s"
            break

        cur_io = _read_proc_io(proc.pid)
        if cur_io is not None and cur_io > last_io:
            last_io = cur_io
            last_progress_at = now
        elif now - last_progress_at > idle_timeout_seconds:
            kill_reason = (
                f"idle for {int(now - last_progress_at)}s "
                f"(no /proc/io progress; likely stuck mc)"
            )
            break

    if kill_reason:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        # Drain any output
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        output_tail = "\n".join(
            p.strip() for p in (stdout, stderr) if p and p.strip()
        )
        msg = kill_reason
        if output_tail:
            msg = f"{kill_reason} | tail: {summarize_message(output_tail)}"
        return False, msg

    stdout = proc.stdout.read() if proc.stdout else ""
    stderr = proc.stderr.read() if proc.stderr else ""
    output = "\n".join(p.strip() for p in (stdout, stderr) if p and p.strip())
    if proc.returncode == 0:
        return True, output or "ok"
    return False, output or f"exit_code={proc.returncode}"


def backoff_sleep(attempt: int, base: int, cap: int) -> float:
    delay = min(base * (2 ** (attempt - 1)), cap)
    jitter = random.uniform(0, delay * 0.25)
    return delay + jitter


def sync_one_prefix(
    prefix: str,
    args: argparse.Namespace,
    state: SyncState,
    log_path: Path,
) -> PrefixResult:
    now_ts = time.time()
    if state.should_skip_success(prefix, now_ts, args.skip_hours * 3600):
        return PrefixResult(prefix, "skipped", 0, "recent success")
    if state.should_skip_failure(
        prefix, now_ts, args.fail_cooldown_min * 60, args.max_retries
    ):
        return PrefixResult(prefix, "skipped", 0, "persistent failure cooldown")

    last_message = ""
    for attempt in range(1, args.max_retries + 1):
        ok, message = run_mirror(
            args.mc_bin,
            args.bucket,
            prefix,
            args.timeout_seconds,
            args.idle_timeout_seconds,
            args.watchdog_interval,
            args.limit_upload,
            args.limit_download,
        )
        if ok:
            state.mark_success(prefix, attempt)
            return PrefixResult(prefix, "success", attempt, message)

        last_message = message
        state.mark_failure(prefix, attempt, message)
        append_log(log_path, prefix, attempt, message)

        if attempt < args.max_retries:
            time.sleep(backoff_sleep(attempt, args.backoff_base, args.backoff_max))

    return PrefixResult(prefix, "failed", args.max_retries, last_message)


def detect_shard_index() -> int | None:
    val = os.environ.get("SHARD_INDEX")
    if val is not None:
        return int(val)
    # POD_NAME from downwardAPI (e.g. mc-client-0); HOSTNAME unreliable under hostNetwork
    pod = os.environ.get("POD_NAME", "")
    tail = pod.rsplit("-", 1)[-1]
    if tail.isdigit():
        return int(tail)
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mirror origin gitlab-lfs-prod prefixes to local. "
        "Runs one prefix at a time; concurrency is controlled by mc itself "
        "(MC_UPLOAD_MULTIPART_THREADS / --limit-upload). "
        "Multi-pod sharding via --shard-index/--shard-total (or SHARD_INDEX env / "
        "StatefulSet ordinal in HOSTNAME)."
    )
    parser.add_argument("--mc-bin", default="/usr/local/bin/mc")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument(
        "--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS,
        help="hard wall-clock ceiling per mc-mirror invocation",
    )
    parser.add_argument(
        "--idle-timeout-seconds", type=int, default=DEFAULT_IDLE_TIMEOUT_SECONDS,
        help="kill mc-mirror if /proc/io has no progress for this many seconds",
    )
    parser.add_argument(
        "--watchdog-interval", type=int, default=DEFAULT_WATCHDOG_INTERVAL_SECONDS,
        help="how often the watchdog samples /proc/io",
    )
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--skip-hours", type=int, default=DEFAULT_SKIP_HOURS)
    parser.add_argument(
        "--fail-cooldown-min",
        type=int,
        default=DEFAULT_FAIL_COOLDOWN_MIN,
        help="skip a prefix that hit max-retries within this many minutes",
    )
    parser.add_argument("--backoff-base", type=int, default=DEFAULT_BACKOFF_BASE)
    parser.add_argument("--backoff-max", type=int, default=DEFAULT_BACKOFF_MAX)
    parser.add_argument("--limit-upload", default=os.environ.get("MC_LIMIT_UPLOAD"))
    parser.add_argument("--limit-download", default=os.environ.get("MC_LIMIT_DOWNLOAD"))
    parser.add_argument(
        "--shard-index", type=int, default=detect_shard_index(),
        help="this pod's shard index (0-based); auto-read from SHARD_INDEX env or HOSTNAME tail",
    )
    parser.add_argument(
        "--shard-total", type=int,
        default=int(os.environ["SHARD_TOTAL"]) if os.environ.get("SHARD_TOTAL") else None,
        help="total number of shards",
    )
    parser.add_argument("--state-file", default="/tmp/gitlab-sync-state.json")
    parser.add_argument("--log-file", default="/tmp/gitlab-sync.log")
    parser.add_argument("--prefixes", nargs="*", help="explicit prefixes; default all 256")
    parser.add_argument("--verbose-skips", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = SyncState(Path(args.state_file))
    log_path = Path(args.log_file)
    all_prefixes = args.prefixes or [f"{i:02x}" for i in range(256)]
    if args.shard_index is not None and args.shard_total:
        prefixes = [
            p for i, p in enumerate(all_prefixes)
            if i % args.shard_total == args.shard_index
        ]
        shard = f"{args.shard_index}/{args.shard_total}"
    else:
        prefixes = all_prefixes
        shard = "all"
    started_at = time.time()

    print(
        f"[{iso_now()}] start bucket={args.bucket} shard={shard} prefixes={len(prefixes)} "
        f"timeout={args.timeout_seconds}s retries={args.max_retries} "
        f"skip_hours={args.skip_hours} fail_cooldown_min={args.fail_cooldown_min} "
        f"limit_up={args.limit_upload} limit_dn={args.limit_download} "
        f"mc_multipart_threads={os.environ.get('MC_UPLOAD_MULTIPART_THREADS', 'default')}"
    )

    success = skipped = failed = 0
    for prefix in prefixes:
        result = sync_one_prefix(prefix, args, state, log_path)
        if result.status == "success":
            success += 1
        elif result.status == "skipped":
            skipped += 1
            if not args.verbose_skips:
                continue
        else:
            failed += 1

        message = result.message
        if result.status == "failed":
            message = summarize_message(result.message)
        print(
            f"[{iso_now()}] prefix={result.prefix} status={result.status} "
            f"attempt={result.attempt} message={message}"
        )

    duration = format_duration(time.time() - started_at)
    print(
        f"[{iso_now()}] done total={len(prefixes)} "
        f"success={success} skipped={skipped} failed={failed} duration={duration}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
