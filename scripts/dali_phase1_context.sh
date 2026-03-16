#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jeebs/src/clawd"
PHASE_DOC="$ROOT/workspace/dali_unreal/Docs/PhaseOneOfflinePipeline.md"
HANDOFF_DOC="$ROOT/workspace/handoffs/dali_phase1_offline_pipeline_2026-03-09.md"
OLD_HANDOFF="$ROOT/workspace/audit/cathedral_ue5_handoff_20260308T123354Z.md"

cd "$ROOT"

echo "=== DALI PHASE ONE CONTEXT ==="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "branch=$(git branch --show-current 2>/dev/null || echo unknown)"
echo "head=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo

echo "git_status_porcelain:"
git status --short || true
echo

echo "service_status:"
systemctl --user status dali-fishtank.service --no-pager --lines=8 || true
echo

echo "runtime_status:"
(cd "$ROOT/workspace" && python3 -m cathedral.control_api status) || true
echo

for path in "$PHASE_DOC" "$HANDOFF_DOC" "$OLD_HANDOFF"; do
  if [[ -f "$path" ]]; then
    echo "===== ${path#$ROOT/} ====="
    sed -n '1,220p' "$path"
    echo
  fi
done
