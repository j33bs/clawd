#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
STATE_DIR="$ROOT_DIR/workspace/local_exec/state"
PID_FILE="$STATE_DIR/worker.pid"
LOG_FILE="$STATE_DIR/worker.log"

WORKER_UNIT_NAME="openclaw-local-exec-worker.service"
VLLM_UNIT_NAME="vllm-local-exec.service"
WORKER_UNIT_TEMPLATE="$ROOT_DIR/workspace/local_exec/systemd/$WORKER_UNIT_NAME"
VLLM_UNIT_TEMPLATE="$ROOT_DIR/workspace/local_exec/systemd/$VLLM_UNIT_NAME"
WORKER_UNIT_DEST="$HOME/.config/systemd/user/$WORKER_UNIT_NAME"
VLLM_UNIT_DEST="$HOME/.config/systemd/user/$VLLM_UNIT_NAME"
LOCAL_EXEC_ENV_FILE="$HOME/.config/openclaw/local_exec.env"

mkdir -p "$STATE_DIR"
cd "$ROOT_DIR"

systemd_user_available() {
  systemctl --user show-environment >/dev/null 2>&1
}

install_units() {
  if ! mkdir -p "$HOME/.config/systemd/user" 2>/dev/null; then
    echo "install_units=blocked reason=systemd_user_dir_unwritable path=$HOME/.config/systemd/user"
    return 0
  fi
  local tmp_worker tmp_vllm
  tmp_worker="$(mktemp)"
  tmp_vllm="$(mktemp)"
  if ! sed "s#__REPO_ROOT__#$ROOT_DIR#g" "$WORKER_UNIT_TEMPLATE" > "$tmp_worker" 2>/dev/null; then
    echo "install_units=blocked reason=worker_unit_write_failed path=$WORKER_UNIT_DEST"
    rm -f "$tmp_worker" "$tmp_vllm"
    return 0
  fi
  if ! sed "s#__REPO_ROOT__#$ROOT_DIR#g" "$VLLM_UNIT_TEMPLATE" > "$tmp_vllm" 2>/dev/null; then
    echo "install_units=blocked reason=vllm_unit_write_failed path=$VLLM_UNIT_DEST"
    rm -f "$tmp_worker" "$tmp_vllm"
    return 0
  fi
  if ! cp "$tmp_worker" "$WORKER_UNIT_DEST" 2>/dev/null; then
    echo "install_units=blocked reason=worker_unit_copy_failed path=$WORKER_UNIT_DEST"
    rm -f "$tmp_worker" "$tmp_vllm"
    return 0
  fi
  if ! cp "$tmp_vllm" "$VLLM_UNIT_DEST" 2>/dev/null; then
    echo "install_units=blocked reason=vllm_unit_copy_failed path=$VLLM_UNIT_DEST"
    rm -f "$tmp_worker" "$tmp_vllm"
    return 0
  fi
  rm -f "$tmp_worker" "$tmp_vllm"
  chmod 0644 "$WORKER_UNIT_DEST" "$VLLM_UNIT_DEST" 2>/dev/null || true
  echo "installed units: $WORKER_UNIT_DEST $VLLM_UNIT_DEST"
}

start_fallback_worker() {
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE")"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "fallback worker already running pid=$pid"
      return 0
    fi
  fi
  nohup python3 -m workspace.local_exec.worker --repo-root "$ROOT_DIR" --loop --sleep-s 2 --max-idle-s 300 --worker-id local-exec-fallback >>"$LOG_FILE" 2>&1 &
  echo "$!" > "$PID_FILE"
  echo "fallback worker started pid=$!"
}

stop_fallback_worker() {
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

status_fallback_worker() {
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE")"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "fallback worker active pid=$pid"
      return 0
    fi
  fi
  echo "fallback worker inactive"
}

start_worker() {
  if systemd_user_available; then
    install_units
    systemctl --user daemon-reload
    systemctl --user enable --now "$WORKER_UNIT_NAME"
    systemctl --user restart "$WORKER_UNIT_NAME"
  else
    start_fallback_worker
  fi
}

stop_worker() {
  if systemd_user_available; then
    systemctl --user stop "$WORKER_UNIT_NAME" || true
  else
    stop_fallback_worker
  fi
}

start_vllm_if_enabled() {
  if [[ "${LOCAL_EXEC_ENABLE_VLLM:-0}" != "1" ]]; then
    echo "vllm_start=skipped reason=LOCAL_EXEC_ENABLE_VLLM_not_set"
    return 0
  fi
  if ! systemd_user_available; then
    echo "vllm_start=blocked reason=systemd_user_unavailable"
    return 0
  fi
  if [[ ! -f "$LOCAL_EXEC_ENV_FILE" ]]; then
    echo "vllm_start=blocked reason=missing_env_file path=$LOCAL_EXEC_ENV_FILE"
    return 0
  fi

  install_units
  systemctl --user daemon-reload
  systemctl --user enable --now "$VLLM_UNIT_NAME" || true
  systemctl --user restart "$VLLM_UNIT_NAME" || true
}

stop_vllm() {
  if systemd_user_available; then
    systemctl --user stop "$VLLM_UNIT_NAME" || true
  else
    echo "vllm_stop=skipped reason=systemd_user_unavailable"
  fi
}

enable_vllm() {
  if ! systemd_user_available; then
    echo "enable_vllm=blocked reason=systemd_user_unavailable"
    return 0
  fi
  if [[ ! -f "$LOCAL_EXEC_ENV_FILE" ]]; then
    echo "enable_vllm=blocked reason=missing_env_file path=$LOCAL_EXEC_ENV_FILE"
    return 0
  fi
  install_units
  systemctl --user daemon-reload
  systemctl --user enable --now "$VLLM_UNIT_NAME"
  systemctl --user restart "$VLLM_UNIT_NAME"
  systemctl --user --no-pager --full status "$VLLM_UNIT_NAME" || true
}

status_all() {
  if systemd_user_available; then
    systemctl --user --no-pager --full status "$WORKER_UNIT_NAME" || true
    systemctl --user --no-pager --full status "$VLLM_UNIT_NAME" || true
  else
    status_fallback_worker
    echo "vllm_status=unknown reason=systemd_user_unavailable"
  fi
}

health_report() {
  python3 - <<'PY'
import json
import os
import urllib.error
import urllib.request
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

model_stub = os.environ.get('OPENCLAW_LOCAL_EXEC_MODEL_STUB', '1') == '1'
api_base = os.environ.get('OPENCLAW_LOCAL_EXEC_API_BASE') or os.environ.get('OPENAI_BASE_URL') or ''
model_reachable = None
model_detail = 'stub_mode'
if not model_stub and api_base:
    url = api_base.rstrip('/') + '/models'
    req = urllib.request.Request(url, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            body = resp.read(2048).decode('utf-8', errors='replace')
        model_reachable = True
        model_detail = f'http_{resp.status}_bytes_{len(body)}'
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        model_reachable = False
        model_detail = f'error:{str(exc)[:120]}'
elif not model_stub:
    model_reachable = False
    model_detail = 'missing_api_base'

payload = {
    'kill_switch': kill_switch.exists(),
    'ledger_path': str(ledger),
    'events': len(rows),
    'last_event': rows[-1] if rows else None,
    'model_stub_mode': model_stub,
    'model_api_base': api_base,
    'model_reachable': model_reachable,
    'model_detail': model_detail,
}
print(json.dumps(payload, ensure_ascii=False))
print(
    f"summary kill_switch={payload['kill_switch']} events={payload['events']} "
    f"model_stub={payload['model_stub_mode']} model_reachable={payload['model_reachable']}"
)
PY
}

cmd="${1:-status}"
case "$cmd" in
  start)
    start_worker
    start_vllm_if_enabled
    status_all
    ;;
  stop)
    stop_worker
    stop_vllm
    status_all
    ;;
  status)
    status_all
    ;;
  health)
    health_report
    ;;
  enqueue-demo)
    python3 "$ROOT_DIR/scripts/local_exec_enqueue.py" --repo-root "$ROOT_DIR" --demo
    ;;
  install-units)
    install_units
    if systemd_user_available; then
      systemctl --user daemon-reload
    fi
    ;;
  enable-vllm)
    enable_vllm
    ;;
  *)
    echo "usage: $0 {start|stop|status|health|enqueue-demo|install-units|enable-vllm}" >&2
    exit 2
    ;;
esac
