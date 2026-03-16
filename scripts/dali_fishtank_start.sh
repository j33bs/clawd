#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_DIR="$ROOT_DIR/workspace"
VENV_DIR="$ROOT_DIR/.venv-dali-fishtank"
PYTHON_BIN="$VENV_DIR/bin/python"
ENV_DIR="$HOME/.config/openclaw"
ENV_FILE="$ENV_DIR/dali-fishtank.env"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SYSTEMD_USER_DIR/dali-fishtank.service"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

resolve_display_default() {
  if [[ -n "${DISPLAY:-}" ]]; then
    local display_num="${DISPLAY#:}"
    if [[ "$display_num" =~ ^[0-9]+$ ]] && [[ -S "/tmp/.X11-unix/X${display_num}" ]]; then
      printf ':%s\n' "$display_num"
      return
    fi
  fi
  local socket_path
  socket_path="$(find /tmp/.X11-unix -maxdepth 1 -type s -name 'X*' 2>/dev/null | sort | head -n1 || true)"
  if [[ -n "$socket_path" ]]; then
    printf ':%s\n' "${socket_path##*X}"
    return
  fi
  printf ':0\n'
}

upsert_default_if_blank() {
  local key="$1"
  local value="$2"
  mkdir -p "$ENV_DIR"
  touch "$ENV_FILE"
  if grep -q "^${key}=" "$ENV_FILE"; then
    local current
    current="$(awk -F= -v k="$key" '$1 == k {sub(/^[^=]*=/, "", $0); print; exit}' "$ENV_FILE")"
    if [[ -z "${current}" ]]; then
      python3 - "$ENV_FILE" "$key" "$value" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
out = []
updated = False
for line in lines:
    if line.startswith(f"{key}=") and not updated:
        out.append(f"{key}={value}")
        updated = True
    else:
        out.append(line)
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
    fi
    return
  fi
  printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
}

upsert_value() {
  local key="$1"
  local value="$2"
  mkdir -p "$ENV_DIR"
  touch "$ENV_FILE"
  python3 - "$ENV_FILE" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
out = []
updated = False
for line in lines:
    if line.startswith(f"{key}=") and not updated:
        out.append(f"{key}={value}")
        updated = True
    else:
        out.append(line)
if not updated:
    out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
}

migrate_legacy_frontend_defaults() {
  mkdir -p "$ENV_DIR"
  touch "$ENV_FILE"
  python3 - "$ENV_FILE" \
    "$ROOT_DIR/workspace/dali_unreal/Saved/StagedBuilds/Linux/DaliMirror.sh" \
    "$ROOT_DIR/scripts/dali_ue5_run_game.sh" \
    "$ROOT_DIR/scripts/dali_phase1_idle_run.sh" \
    "$ROOT_DIR/workspace/runtime/phase1_idle_status.json" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
legacy_ue5_launcher = sys.argv[2]
new_ue5_launcher = sys.argv[3]
phase1_launcher = sys.argv[4]
phase1_status_path = sys.argv[5]

lines = path.read_text(encoding="utf-8").splitlines()
values = {}
indexes = {}
for idx, line in enumerate(lines):
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    if key in indexes:
        continue
    values[key] = value.strip()
    indexes[key] = idx

frontend = values.get("DALI_FISHTANK_FRONTEND", "")
ue5_launcher = values.get("DALI_FISHTANK_UE5_LAUNCHER", "")
legacy_phase1_migration = frontend == "ue5" and ue5_launcher == legacy_ue5_launcher
if ue5_launcher == legacy_ue5_launcher and "DALI_FISHTANK_UE5_LAUNCHER" in indexes:
    lines[indexes["DALI_FISHTANK_UE5_LAUNCHER"]] = f"DALI_FISHTANK_UE5_LAUNCHER={new_ue5_launcher}"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    values["DALI_FISHTANK_UE5_LAUNCHER"] = new_ue5_launcher
    ue5_launcher = new_ue5_launcher

if not legacy_phase1_migration:
    raise SystemExit(0)

lines[indexes["DALI_FISHTANK_FRONTEND"]] = "DALI_FISHTANK_FRONTEND=phase1"
if "DALI_FISHTANK_PHASE1_LAUNCHER" in indexes:
    lines[indexes["DALI_FISHTANK_PHASE1_LAUNCHER"]] = f"DALI_FISHTANK_PHASE1_LAUNCHER={phase1_launcher}"
else:
    lines.append(f"DALI_FISHTANK_PHASE1_LAUNCHER={phase1_launcher}")
if "DALI_FISHTANK_PHASE1_STATUS_PATH" in indexes:
    lines[indexes["DALI_FISHTANK_PHASE1_STATUS_PATH"]] = f"DALI_FISHTANK_PHASE1_STATUS_PATH={phase1_status_path}"
else:
    lines.append(f"DALI_FISHTANK_PHASE1_STATUS_PATH={phase1_status_path}")

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

reconcile_session_display_defaults() {
  local display_value="$1"
  local xauthority_value="$2"
  local runtime_dir_value="$3"
  local dbus_value="$4"
  local session_type_value="$5"
  python3 - "$ENV_FILE" "$display_value" "$xauthority_value" "$runtime_dir_value" "$dbus_value" "$session_type_value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
display_value = sys.argv[2].strip()
xauthority_value = sys.argv[3].strip()
runtime_dir_value = sys.argv[4].strip()
dbus_value = sys.argv[5].strip()
session_type_value = sys.argv[6].strip()

if not path.exists():
    raise SystemExit(0)

lines = path.read_text(encoding="utf-8").splitlines()
indexes = {}
values = {}
for idx, line in enumerate(lines):
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    if key in indexes:
        continue
    indexes[key] = idx
    values[key] = value.strip()

def display_socket_exists(value: str) -> bool:
    if not value:
        return False
    if value.startswith(":") and value[1:].isdigit():
        return Path(f"/tmp/.X11-unix/X{value[1:]}").exists()
    return True

def set_value(key: str, value: str) -> None:
    if key in indexes:
        lines[indexes[key]] = f"{key}={value}"
    else:
        lines.append(f"{key}={value}")

configured_display = values.get("DISPLAY", "")
if display_socket_exists(display_value) and not display_socket_exists(configured_display):
    set_value("DISPLAY", display_value)

configured_xauthority = values.get("XAUTHORITY", "")
if xauthority_value and Path(xauthority_value).exists() and (not configured_xauthority or not Path(configured_xauthority).exists()):
    set_value("XAUTHORITY", xauthority_value)

if runtime_dir_value and Path(runtime_dir_value).exists() and not values.get("XDG_RUNTIME_DIR", ""):
    set_value("XDG_RUNTIME_DIR", runtime_dir_value)

if dbus_value and not values.get("DBUS_SESSION_BUS_ADDRESS", ""):
    set_value("DBUS_SESSION_BUS_ADDRESS", dbus_value)

if session_type_value and not values.get("XDG_SESSION_TYPE", ""):
    set_value("XDG_SESSION_TYPE", session_type_value)

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

write_env_defaults() {
  local runtime_dir_default="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  local dbus_default="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$runtime_dir_default/bus}"
  local display_default
  display_default="$(resolve_display_default)"
  local session_type_default="${XDG_SESSION_TYPE:-x11}"
  local xauthority_default="${XAUTHORITY:-$HOME/.Xauthority}"
  local lang_default="${LANG:-C.UTF-8}"

  mkdir -p "$ENV_DIR"
  touch "$ENV_FILE"
  if ! grep -q "^# Generated by scripts/dali_fishtank_start.sh" "$ENV_FILE" 2>/dev/null; then
    {
      echo "# Generated by scripts/dali_fishtank_start.sh"
      cat "$ENV_FILE"
    } > "${ENV_FILE}.tmp"
    mv "${ENV_FILE}.tmp" "$ENV_FILE"
  fi

  reconcile_session_display_defaults \
    "$display_default" \
    "$xauthority_default" \
    "$runtime_dir_default" \
    "$dbus_default" \
    "$session_type_default"

  upsert_default_if_blank "PYTHONUNBUFFERED" "1"
  upsert_default_if_blank "PYTHONPATH" "$WORKSPACE_DIR"
  upsert_value "DISPLAY" "$display_default"
  upsert_value "XDG_RUNTIME_DIR" "$runtime_dir_default"
  upsert_value "DBUS_SESSION_BUS_ADDRESS" "$dbus_default"
  upsert_value "XDG_SESSION_TYPE" "$session_type_default"
  if [[ -n "$xauthority_default" && -e "$xauthority_default" ]]; then
    upsert_value "XAUTHORITY" "$xauthority_default"
  else
    upsert_default_if_blank "XAUTHORITY" "$xauthority_default"
  fi
  upsert_default_if_blank "LANG" "$lang_default"
  upsert_default_if_blank "DALI_FISHTANK_RATE_HZ" "30"
  upsert_default_if_blank "DALI_FISHTANK_TELEMETRY_HZ" "6"
  upsert_default_if_blank "DALI_FISHTANK_TACTI_HZ" "2"
  upsert_default_if_blank "DALI_FISHTANK_AGENT_COUNT" "120000"
  upsert_default_if_blank "DALI_FISHTANK_HEADLESS" "0"
  upsert_default_if_blank "DALI_FISHTANK_HEADLESS_CONSUMER" ""
  upsert_default_if_blank "DALI_FISHTANK_FULLSCREEN" "1"
  upsert_default_if_blank "DALI_FISHTANK_REQUIRE_GPU" "1"
  upsert_default_if_blank "DALI_FISHTANK_TELEGRAM_ENABLED" "1"
  upsert_default_if_blank "DALI_FISHTANK_TELEGRAM_AUTOCLEAR_WEBHOOK" "0"
  upsert_default_if_blank "DALI_FISHTANK_TELEGRAM_TOKEN" ""
  upsert_default_if_blank "DALI_FISHTANK_TELEGRAM_ALLOWLIST" ""
  upsert_default_if_blank "DALI_FISHTANK_TELEGRAM_DEBUG_DRAIN" "0"
  upsert_default_if_blank "DALI_FISHTANK_TELEGRAM_REQUIRED" "0"
  upsert_default_if_blank "DALI_FISHTANK_EXPOSURE_BASE" "1.6"
  upsert_default_if_blank "DALI_FISHTANK_BLOOM" "0.45"
  upsert_default_if_blank "DALI_FISHTANK_PARTICLES_TARGET" "180000"
  upsert_default_if_blank "DALI_FISHTANK_CONTRAST" "1.08"
  upsert_default_if_blank "DALI_FISHTANK_SATURATION" "1.05"
  upsert_default_if_blank "DALI_FISHTANK_BLOOM_STRENGTH" "0.6"
  upsert_default_if_blank "DALI_FISHTANK_BLOOM_THRESHOLD" "0.32"
  upsert_default_if_blank "DALI_FISHTANK_BLOOM_KNEE" "0.28"
  upsert_default_if_blank "DALI_FISHTANK_TONEMAP" "aces"
  upsert_default_if_blank "DALI_FISHTANK_HDR_CLAMP" "10.0"
  upsert_default_if_blank "DALI_FISHTANK_PALETTE_MODE" "dali"
  upsert_default_if_blank "DALI_FISHTANK_PRESET" "cathedral_soft"
  upsert_default_if_blank "DALI_FISHTANK_WHITE_BALANCE_R" "0.98"
  upsert_default_if_blank "DALI_FISHTANK_WHITE_BALANCE_G" "0.94"
  upsert_default_if_blank "DALI_FISHTANK_WHITE_BALANCE_B" "1.12"
  upsert_default_if_blank "DALI_FISHTANK_LAYER_WEIGHT_PARTICLES" "0.34"
  upsert_default_if_blank "DALI_FISHTANK_LAYER_WEIGHT_RD" "1.12"
  upsert_default_if_blank "DALI_FISHTANK_LAYER_WEIGHT_VOLUME" "1.34"
  upsert_default_if_blank "DALI_FISHTANK_RD_ENABLED" "1"
  upsert_default_if_blank "DALI_FISHTANK_VOL_ENABLED" "1"
  upsert_default_if_blank "DALI_FISHTANK_TEMPORAL_ENABLED" "1"
  upsert_default_if_blank "DALI_FISHTANK_RD_RES" "768"
  upsert_default_if_blank "DALI_FISHTANK_VOL_STEPS" "48"
  upsert_default_if_blank "DALI_FISHTANK_TEMPORAL_ALPHA" "0.92"
  upsert_default_if_blank "DALI_FISHTANK_GPU_LEASE_MODE" "exclusive"
  upsert_default_if_blank "DALI_FISHTANK_GPU_LEASE_TTL_S" "20"
  upsert_default_if_blank "DALI_FISHTANK_QUIESCE_INFERENCE" "1"
  upsert_default_if_blank "DALI_FISHTANK_QUIESCE_UNITS" "openclaw-dali-heavy-node.service"
  upsert_default_if_blank "DALI_FISHTANK_QUIESCE_ENDPOINT" ""
  upsert_default_if_blank "DALI_FISHTANK_IDLE_ENABLE" "1"
  upsert_default_if_blank "DALI_FISHTANK_IDLE_SECONDS" "30"
  upsert_default_if_blank "DALI_FISHTANK_IDLE_INHIBIT" "1"
  upsert_default_if_blank "DALI_FISHTANK_IDLE_TRIGGER_SOURCE" "session"
  upsert_default_if_blank "DALI_FISHTANK_ENTER_DISPLAY_MODE" "0"
  upsert_default_if_blank "DALI_FISHTANK_SCHEDULE_ENABLED" "1"
  upsert_default_if_blank "DALI_FISHTANK_SCHEDULE_SLOTS" "fri:17:00-sun:23:00,mon:17:00-mon:21:00,tue:17:00-tue:21:00"
  upsert_default_if_blank "DALI_FISHTANK_SCHEDULE_START" "17:00"
  upsert_default_if_blank "DALI_FISHTANK_SCHEDULE_END" "21:00"
  upsert_default_if_blank "DALI_FISHTANK_TIMEZONE" "Australia/Brisbane"
  upsert_default_if_blank "DALI_FISHTANK_IDENTITY_PROFILE" "dali"
  upsert_default_if_blank "DALI_FISHTANK_SCHEDULE_LATCH_DISPLAY" "0"
  upsert_default_if_blank "DALI_FISHTANK_DISPLAY_RATE_MODE" "monitor"
  upsert_default_if_blank "DALI_FISHTANK_DISPLAY_RATE_HZ" "120"
  upsert_default_if_blank "DALI_FISHTANK_FRONTEND" "python"
  upsert_default_if_blank "DALI_FISHTANK_UE5_LAUNCHER" "$ROOT_DIR/scripts/dali_ue5_run_game.sh"
  upsert_default_if_blank "DALI_FISHTANK_PHASE1_LAUNCHER" "$ROOT_DIR/scripts/dali_phase1_idle_run.sh"
  upsert_default_if_blank "DALI_FISHTANK_PHASE1_STATUS_PATH" "$ROOT_DIR/workspace/runtime/phase1_idle_status.json"
  upsert_default_if_blank "DALI_FISHTANK_PHASE1_IDLE_AUTORUN" "0"
  upsert_default_if_blank "DALI_FISHTANK_PHASE1_OUTPUT_ROOT" ""
  upsert_default_if_blank "DALI_FISHTANK_PHASE1_GRID" ""
  upsert_default_if_blank "DALI_FISHTANK_PHASE1_MAX_STEPS" ""
  upsert_default_if_blank "DALI_FISHTANK_PHASE1_BATCH_SIZE" ""
  upsert_default_if_blank "DALI_FISHTANK_PHASE1_CHECKPOINT_EVERY" ""
  upsert_default_if_blank "DALI_FISHTANK_PHASE1_SEED" ""
  upsert_default_if_blank "DALI_FISHTANK_FRONTEND_SUCCESS_RESET_S" "15"
  upsert_default_if_blank "DALI_FISHTANK_FRONTEND_RESTART_CAP_S" "60"
  upsert_default_if_blank "DALI_FISHTANK_ALLOW_PYTHON_VISIBLE_ATTACH" "0"
  upsert_default_if_blank "DALI_FISHTANK_SWAP_INTERVAL" "1"
  upsert_default_if_blank "DALI_FISHTANK_PRESENT_EXPERIMENT" "off"
  upsert_default_if_blank "DALI_FISHTANK_PRESENT_RATE_CAP_OVERRIDE_HZ" "0"
  upsert_default_if_blank "DALI_FISHTANK_ABORT_IF_FULLSCREEN_ACTIVE" "1"
  migrate_legacy_frontend_defaults
}

bootstrap_venv() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log "creating_venv path=$VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi
}

run_runtime() {
  write_env_defaults
  bootstrap_venv
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  export PYTHONUNBUFFERED=1
  export PYTHONPATH="${PYTHONPATH:-$WORKSPACE_DIR}"
  exec "$PYTHON_BIN" -m cathedral.runtime "$@"
}

install_units() {
  write_env_defaults
  mkdir -p "$SYSTEMD_USER_DIR"
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=DALI Consciousness Mirror FishTank runtime
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=45
StartLimitBurst=8

[Service]
Type=simple
WorkingDirectory=%h/src/clawd
EnvironmentFile=%h/.config/openclaw/dali-fishtank.env
ExecStart=%h/src/clawd/scripts/dali_fishtank_start.sh run
Restart=on-failure
RestartSec=2
Nice=10
CPUWeight=20
IOWeight=20
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK
NoNewPrivileges=true
StandardOutput=append:%h/.local/state/openclaw/dali-fishtank.log
StandardError=append:%h/.local/state/openclaw/dali-fishtank.log

[Install]
WantedBy=default.target
EOF

  install -m 0644 "$ROOT_DIR/workspace/systemd/dali-fishtank-window-start.service" "$SYSTEMD_USER_DIR/dali-fishtank-window-start.service"
  install -m 0644 "$ROOT_DIR/workspace/systemd/dali-fishtank-window-start.timer" "$SYSTEMD_USER_DIR/dali-fishtank-window-start.timer"
  install -m 0644 "$ROOT_DIR/workspace/systemd/dali-fishtank-window-end.service" "$SYSTEMD_USER_DIR/dali-fishtank-window-end.service"
  install -m 0644 "$ROOT_DIR/workspace/systemd/dali-fishtank-window-end.timer" "$SYSTEMD_USER_DIR/dali-fishtank-window-end.timer"
  log "installed_units dir=$SYSTEMD_USER_DIR"
}

control_mode() {
  write_env_defaults
  local subcommand="${1:-status}"
  shift || true
  export PYTHONPATH="$WORKSPACE_DIR"
  case "$subcommand" in
    status|on|off|auto)
      exec "$PYTHON_BIN" -m cathedral.control_api "$subcommand" "$@"
      ;;
    nudge-start)
      exec "$PYTHON_BIN" - <<'PY'
from cathedral.control_api import record_schedule_nudge
import json
print(json.dumps(record_schedule_nudge("window_start", source="systemd"), ensure_ascii=True, sort_keys=True))
PY
      ;;
    nudge-end)
      exec "$PYTHON_BIN" - <<'PY'
from cathedral.control_api import record_schedule_nudge
import json
print(json.dumps(record_schedule_nudge("window_end", source="systemd"), ensure_ascii=True, sort_keys=True))
PY
      ;;
    *)
      echo "usage: $0 control {status|on|off|auto|nudge-start|nudge-end}" >&2
      exit 2
      ;;
  esac
}

command="${1:-run}"
shift || true

case "$command" in
  bootstrap)
    write_env_defaults
    bootstrap_venv
    ;;
  install)
    install_units
    ;;
  run)
    run_runtime "$@"
    ;;
  control)
    control_mode "$@"
    ;;
  *)
    echo "usage: $0 {bootstrap|install|run|control}" >&2
    exit 2
    ;;
esac
