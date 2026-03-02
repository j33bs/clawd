#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

LOGDIR="$ROOT/workspace/logs/tools"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/mcp.qmd.http.log"

CMD="${OPENCLAW_TOOL_CMD_MCP_QMD_HTTP:-}"

if [ -z "$CMD" ]; then
  # Candidate: system2_http_edge.js (if it matches your intent)
  if [ -f "$ROOT/scripts/system2_http_edge.js" ]; then
    # Only a fallback; real port binding must be ensured by the command/env.
    CMD="node $ROOT/scripts/system2_http_edge.js"
  fi
fi

if [ -z "$CMD" ]; then
  echo "ERROR: No start command configured for mcp.qmd.http" | tee -a "$LOG"
  echo "Set OPENCLAW_TOOL_CMD_MCP_QMD_HTTP in ~/.config/openclaw/tools.env" | tee -a "$LOG"
  exit 2
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] exec: $CMD" | tee -a "$LOG"
exec bash -lc "$CMD" 2>&1 | tee -a "$LOG"
