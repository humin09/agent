#!/bin/bash
export PATH="/opt/homebrew/bin:$PATH"
export HOME="/Users/humin"

MSG="麻烦大家更新周报"
K8S_GROUP="oc_82cb8e617610dab7df3414dd27ed995b"
TEAM3_GROUP="oc_3eaa553b289f47c4165f107d73a053d2"
LOG="/tmp/weekly_reminder.log"

echo "$(date) - Sending weekly reminder..." >> "$LOG"

lark-cli im +messages-send --chat-id "$K8S_GROUP" --text "$MSG" --as bot 2>&1 >> "$LOG"
lark-cli im +messages-send --chat-id "$TEAM3_GROUP" --text "$MSG" --as bot 2>&1 >> "$LOG"

echo "$(date) - Done." >> "$LOG"
