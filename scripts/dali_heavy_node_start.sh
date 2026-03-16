#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/workspace/runtime/heavy_node/.venv/bin/python"
PID_DIR="$ROOT_DIR/workspace/runtime/heavy_node/.run"
PID_FILE="$PID_DIR/dali_heavy_node.pid"
LOG_FILE="$ROOT_DIR/workspace/logs/dali_heavy_node_uvicorn.log"
HOST="${DALI_HEAVY_NODE_HOST:-0.0.0.0}"
PORT="${DALI_HEAVY_NODE_PORT:-18891}"
UNIT_NAME="openclaw-dali-heavy-node.service"

mkdir -p "$PID_DIR" "$(dirname "$LOG_FILE")"

systemd_user_available() {
  command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1
}

if systemd_user_available && systemctl --user cat "$UNIT_NAME" >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user enable --now "$UNIT_NAME"
  echo "started_via_systemd unit=$UNIT_NAME"
  exit 0
fi

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "already_running pid=$PID host=$HOST port=$PORT"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

if [[ ! -x "$VENV_PY" ]]; then
  echo "missing_runtime_venv path=$VENV_PY"
  exit 1
fi

nohup "$VENV_PY" -m uvicorn workspace.runtime.heavy_node.server:app --host "$HOST" --port "$PORT" >>"$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" >"$PID_FILE"
sleep 1

if kill -0 "$PID" 2>/dev/null; then
  echo "started pid=$PID host=$HOST port=$PORT log=$LOG_FILE"
  exit 0
fi

echo "start_failed log=$LOG_FILE"
exit 1
