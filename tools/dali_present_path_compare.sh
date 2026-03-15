#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${HOME}/.config/openclaw/dali-fishtank.env"
STATE_FILE="$ROOT_DIR/workspace/runtime/fishtank_state.json"
OUT_DIR="${1:-$ROOT_DIR/workspace/audit/_evidence/cathedral_present_compare_$(date -u +%Y%m%dT%H%M%SZ)}"
SERVICE="dali-fishtank.service"

mkdir -p "$OUT_DIR"
[[ -f "$ENV_FILE" ]] || { echo "missing env file: $ENV_FILE" >&2; exit 2; }
[[ -f "$STATE_FILE" ]] || true

BACKUP="$OUT_DIR/dali-fishtank.env.backup"
cp "$ENV_FILE" "$BACKUP"

set_env() {
  local key="$1"
  local value="$2"
  python3 - "$ENV_FILE" "$key" "$value" <<PY
from pathlib import Path
import sys
path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
out = []
seen = False
for line in lines:
    if line.startswith(f"{key}="):
        out.append(f"{key}={value}")
        seen = True
    else:
        out.append(line)
if not seen:
    out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
}

collect_state() {
  local label="$1"
  cp "$STATE_FILE" "$OUT_DIR/${label}.state.json"
  python3 - "$OUT_DIR/${label}.state.json" "$OUT_DIR/${label}.summary.json" <<PY
import json
from pathlib import Path
import sys
state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
keys = [
    "swap_interval",
    "present_strategy",
    "present_strategy_detail",
    "monitor_refresh_hz",
    "selected_refresh_hz",
    "loop_rate_target_hz",
    "loop_rate_source",
    "loop_sleep_ms",
    "rate_limited",
    "present_pacing_hz_estimate",
    "present_vs_refresh_ratio",
    "present_path_diagnosis",
    "render_bound_mode",
    "bottleneck_stage",
    "bottleneck_ms",
    "driver_wait_ms",
    "frame_cpu_ms",
    "stage_timings_ms",
    "stage_timings_avg_ms",
    "renderer_fps",
]
summary = {k: state.get(k) for k in keys}
Path(sys.argv[2]).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

restore_env() {
  cp "$BACKUP" "$ENV_FILE"
  systemctl --user restart "$SERVICE" >/dev/null
  "$ROOT_DIR/tools/cathedralctl" fishtank auto --wait-timeout 8 >/dev/null || true
}
trap restore_env EXIT

run_case() {
  local label="$1"
  local swap="$2"
  set_env "DALI_FISHTANK_SWAP_INTERVAL" "$swap"
  set_env "DALI_FISHTANK_PRESENT_EXPERIMENT" "$label"
  set_env "DALI_FISHTANK_PRESENT_RATE_CAP_OVERRIDE_HZ" "0"

  systemctl --user restart "$SERVICE" >/dev/null
  "$ROOT_DIR/tools/cathedralctl" fishtank on --wait-visible --wait-timeout 12 >/dev/null
  sleep 8
  collect_state "$label"
}

run_case "swap1_vsync" "1"
run_case "swap0_uncapped" "0"

echo "wrote present comparison bundle: $OUT_DIR"
