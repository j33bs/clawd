#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_FILE="$ROOT_DIR/workspace/runtime/fishtank_state.json"

run_ctl() {
  "$ROOT_DIR/tools/cathedralctl" fishtank "$@"
}

echo "REPRO_STEP on_wait_visible"
run_ctl on --wait-visible --wait-timeout 8

echo "REPRO_STEP off_wait_hidden"
run_ctl off --wait-hidden --wait-timeout 8

echo "REPRO_STEP auto"
run_ctl auto --wait-timeout 5

echo "REPRO_STEP idle_diagnostics"
python3 - "$STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
keys = [
    "runtime_instance_id",
    "pid",
    "requested_mode",
    "effective_mode",
    "effective_activation_source",
    "idle_source",
    "idle_supported",
    "session_idle_seconds",
    "idle_triggered",
    "display_mode_active",
    "display_attached",
    "window_visible",
    "fullscreen_attached",
    "monitor_bound",
    "last_display_attach_ts",
    "last_display_detach_ts",
]
for key in keys:
    print(f"{key}={payload.get(key)}")
PY
