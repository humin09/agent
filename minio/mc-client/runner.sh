#!/bin/sh
set -eu

LOCK_DIR="/tmp/gitlab-lfs-sync.lock"

while true; do
  if mkdir "${LOCK_DIR}" 2>/dev/null; then
    trap 'rmdir "${LOCK_DIR}"' EXIT INT TERM
    python3 /scripts/gitlab_lfs_sync.py || true
    rmdir "${LOCK_DIR}"
    trap - EXIT INT TERM
  else
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] sync still running, skip this round"
  fi

  sleep 900
done
