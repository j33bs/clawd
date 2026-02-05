#!/bin/bash
# Session log cleanup for OpenClaw
# Compresses logs older than 7 days, deletes compressed logs older than 30 days
# Run manually or via cron: 0 3 * * 0 ~/clawd/scripts/cleanup-session-logs.sh

set -e

LOG_DIR="$HOME/.openclaw/agents/main/sessions"

if [ ! -d "$LOG_DIR" ]; then
  echo "Log directory not found: $LOG_DIR"
  exit 1
fi

# Compress logs older than 7 days
find "$LOG_DIR" -name "*.jsonl" -mtime +7 -exec gzip -v {} \;

# Delete compressed logs older than 30 days
find "$LOG_DIR" -name "*.jsonl.gz" -mtime +30 -delete -print

echo "Cleanup complete."
