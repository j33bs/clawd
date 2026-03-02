#!/usr/bin/env bash
set -u

echo "=== writer_hunt_snapshot ==="
echo "timestamp_utc: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"

echo "--- git_status_porcelain ---"
git status --porcelain || true

echo "--- git_diff_name_only ---"
git diff --name-only || true

echo "--- lsof_listen_18789 ---"
lsof -nP -iTCP:18789 -sTCP:LISTEN || true

echo "--- lsof_target_files ---"
for p in \
  "workspace/state/tacti_cr/events.jsonl" \
  "workspace/research/findings.json" \
  "workspace/research/queue.json" \
  "workspace/research/wander_log.md" \
  "workspace/knowledge_base/data/entities.jsonl" \
  "workspace/knowledge_base/data/last_sync.txt"; do
  echo "path: $p"
  lsof "$p" 2>/dev/null || true
  echo "--"
done

echo "--- ps_filtered ---"
ps aux | egrep -i "openclaw|wander|research|tacti|gateway|mcp|qmd|policy_router" | grep -v egrep || true

echo "--- launchctl_filtered ---"
launchctl list | egrep -i "openclaw|tacti|wander|research|mcp|qmd" || true
