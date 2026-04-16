#!/bin/zsh
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

log="$HOME/agent/scripts/daily-upgrade.log"
echo "=== $(date) ===" >> "$log"

brew upgrade >> "$log" 2>&1
npm update -g >> "$log" 2>&1
claude upgrade >> "$log" 2>&1

echo "" >> "$log"
