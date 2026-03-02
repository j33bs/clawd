#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

LOGDIR="$ROOT/workspace/logs/tools"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/ain.phi.log"

CMD="${OPENCLAW_TOOL_CMD_AIN_PHI:-}"

if [ -z "$CMD" ]; then
  if [ -f "$ROOT/scripts/run_ain_phi.sh" ]; then
    CMD="bash $ROOT/scripts/run_ain_phi.sh"
  elif [ -f "$ROOT/workspace/scripts/run_ain_phi.sh" ]; then
    CMD="bash $ROOT/workspace/scripts/run_ain_phi.sh"
  fi
fi

if [ -z "$CMD" ]; then
  echo "ERROR: No start command configured for ain.phi" | tee -a "$LOG"
  echo "Set OPENCLAW_TOOL_CMD_AIN_PHI in ~/.config/openclaw/tools.env" | tee -a "$LOG"
  exit 2
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] exec: $CMD" | tee -a "$LOG"
exec bash -lc "$CMD" 2>&1 | tee -a "$LOG"
