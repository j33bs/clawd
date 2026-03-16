#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/workspace/runtime/heavy_node/.run/dali_heavy_node.pid"
PORT="${DALI_HEAVY_NODE_PORT:-18891}"
URL="${DALI_HEAVY_NODE_URL:-http://127.0.0.1:${PORT}}"
UNIT_NAME="openclaw-dali-heavy-node.service"

systemd_user_available() {
  command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1
}

if systemd_user_available && systemctl --user cat "$UNIT_NAME" >/dev/null 2>&1; then
  if systemctl --user is-active --quiet "$UNIT_NAME"; then
    echo "systemd=active unit=$UNIT_NAME"
  else
    echo "systemd=inactive unit=$UNIT_NAME"
  fi
fi

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "process=running pid=$PID"
  else
    echo "process=stale"
  fi
else
  echo "process=stopped"
fi

if curl -fsS -m 3 "$URL/health" >/dev/null 2>&1; then
  echo "health=ok url=$URL/health"
else
  echo "health=unreachable url=$URL/health"
fi
