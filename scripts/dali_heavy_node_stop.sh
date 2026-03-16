#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/workspace/runtime/heavy_node/.run/dali_heavy_node.pid"
UNIT_NAME="openclaw-dali-heavy-node.service"

systemd_user_available() {
  command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1
}

if systemd_user_available && systemctl --user cat "$UNIT_NAME" >/dev/null 2>&1; then
  systemctl --user disable --now "$UNIT_NAME" || true
  echo "stopped_via_systemd unit=$UNIT_NAME"
  exit 0
fi

if [[ ! -f "$PID_FILE" ]]; then
  echo "not_running"
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -z "${PID:-}" ]]; then
  rm -f "$PID_FILE"
  echo "not_running"
  exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
  kill "$PID" || true
  sleep 1
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID" || true
  fi
  echo "stopped pid=$PID"
else
  echo "stale_pid pid=$PID"
fi

rm -f "$PID_FILE"
