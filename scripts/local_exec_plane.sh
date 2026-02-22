#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
STATE_DIR="$ROOT_DIR/workspace/local_exec/state"
PID_FILE="$STATE_DIR/worker.pid"
LOG_FILE="$STATE_DIR/worker.log"
UNIT_NAME="openclaw-local-exec-worker.service"
UNIT_TEMPLATE="$ROOT_DIR/workspace/local_exec/systemd/$UNIT_NAME"
UNIT_DEST="$HOME/.config/systemd/user/$UNIT_NAME"

mkdir -p "$STATE_DIR"
cd "$ROOT_DIR"

systemd_user_available() {
  systemctl --user show-environment >/dev/null 2>&1
}

install_unit() {
  mkdir -p "$HOME/.config/systemd/user"
  sed "s#__REPO_ROOT__#$ROOT_DIR#g" "$UNIT_TEMPLATE" > "$UNIT_DEST"
  chmod 0644 "$UNIT_DEST"
}

start_fallback() {
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE")"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "fallback worker already running pid=$pid"
      return 0
    fi
  fi
  nohup python3 -m workspace.local_exec.worker --repo-root "$ROOT_DIR" --worker-id local-exec-fallback >>"$LOG_FILE" 2>&1 &
  echo "$!" > "$PID_FILE"
  echo "fallback worker started pid=$!"
}

stop_fallback() {
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE")"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid"
      echo "fallback worker stopped pid=$pid"
    fi
    rm -f "$PID_FILE"
  else
    echo "fallback worker not running"
  fi
}

status_fallback() {
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE")"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "fallback worker active pid=$pid"
      return 0
    fi
  fi
  echo "fallback worker inactive"
}

health_report() {
  python3 - <<'PY'
import json
from pathlib import Path

root = Path('.').resolve()
ledger = root / 'workspace' / 'local_exec' / 'state' / 'jobs.jsonl'
kill_switch = root / 'workspace' / 'local_exec' / 'state' / 'KILL_SWITCH'
rows = []
if ledger.exists():
    for line in ledger.read_text(encoding='utf-8').splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
print(json.dumps({
    'kill_switch': kill_switch.exists(),
    'ledger_path': str(ledger),
    'events': len(rows),
    'last_event': rows[-1] if rows else None,
}, ensure_ascii=False))
PY
}

cmd="${1:-status}"
case "$cmd" in
  start)
    if systemd_user_available; then
      install_unit
      systemctl --user daemon-reload
      systemctl --user enable --now "$UNIT_NAME"
      systemctl --user restart "$UNIT_NAME"
      systemctl --user --no-pager --full status "$UNIT_NAME" || true
    else
      start_fallback
    fi
    ;;
  stop)
    if systemd_user_available; then
      systemctl --user stop "$UNIT_NAME" || true
      systemctl --user --no-pager --full status "$UNIT_NAME" || true
    else
      stop_fallback
    fi
    ;;
  status)
    if systemd_user_available; then
      systemctl --user --no-pager --full status "$UNIT_NAME" || true
    else
      status_fallback
    fi
    ;;
  health)
    health_report
    ;;
  enqueue-demo)
    python3 "$ROOT_DIR/scripts/local_exec_enqueue.py" --repo-root "$ROOT_DIR" --demo
    ;;
  *)
    echo "usage: $0 {start|stop|status|health|enqueue-demo}" >&2
    exit 2
    ;;
esac
