#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

LOGDIR="$ROOT/workspace/logs/tools"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/coder_vllm.models.log"

# Primary: explicit command override
CMD="${OPENCLAW_TOOL_CMD_CODER_VLLM_MODELS:-}"

# Secondary: conservative heuristic (only if present)
if [ -z "$CMD" ]; then
  if [ -f "$ROOT/scripts/run_coder_vllm_models.sh" ]; then
    CMD="bash $ROOT/scripts/run_coder_vllm_models.sh"
  elif [ -f "$ROOT/workspace/scripts/run_coder_vllm_models.sh" ]; then
    CMD="bash $ROOT/workspace/scripts/run_coder_vllm_models.sh"
  fi
fi

if [ -z "$CMD" ]; then
  echo "ERROR: No start command configured for coder_vllm.models" | tee -a "$LOG"
  echo "Set OPENCLAW_TOOL_CMD_CODER_VLLM_MODELS in ~/.config/openclaw/tools.env" | tee -a "$LOG"
  exit 2
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] exec: $CMD" | tee -a "$LOG"
exec bash -lc "$CMD" 2>&1 | tee -a "$LOG"
