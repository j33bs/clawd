#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DALI_SERVICE="dali-fishtank.service"
WINDOW_START_TIMER="dali-fishtank-window-start.timer"
WINDOW_END_TIMER="dali-fishtank-window-end.timer"
ENV_FILE="$HOME/.config/openclaw/dali-fishtank.env"

STOP_LEGACY=1
MASK_LEGACY=0
for arg in "$@"; do
  case "$arg" in
    --keep-legacy)
      STOP_LEGACY=0
      ;;
    --mask-legacy)
      MASK_LEGACY=1
      ;;
    *)
      echo "usage: $0 [--keep-legacy] [--mask-legacy]" >&2
      exit 1
      ;;
  esac
done

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

check_gpu_runtime_libs() {
  python3 - <<'PY'
import ctypes
import sys

missing = []
try:
    ctypes.CDLL("libGL.so")
except OSError:
    missing.append("libGL.so")
try:
    ctypes.CDLL("libEGL.so")
except OSError:
    missing.append("libEGL.so")

if missing:
    print("CHECK_FAIL gpu_runtime_libs_missing=" + ",".join(missing))
    sys.exit(3)

print("CHECK_OK gpu_runtime_libs_present")
PY
}

check_telegram_env_actionable() {
  local enabled token allowlist
  enabled="$(awk -F= '/^DALI_FISHTANK_TELEGRAM_ENABLED=/{print $2}' "$ENV_FILE" | tail -n1)"
  token="$(awk -F= '/^DALI_FISHTANK_TELEGRAM_TOKEN=/{print $2}' "$ENV_FILE" | tail -n1)"
  allowlist="$(awk -F= '/^DALI_FISHTANK_TELEGRAM_ALLOWLIST=/{print $2}' "$ENV_FILE" | tail -n1)"

  if [[ "$enabled" == "0" ]]; then
    log "telegram_disabled_by_env path=$ENV_FILE"
    return 0
  fi
  if [[ -n "$token" && -n "$allowlist" ]]; then
    log "telegram_env_present path=$ENV_FILE"
    return 0
  fi

  cat <<EOF
========================================================================
TELEGRAM ACTION REQUIRED
env file: $ENV_FILE
missing: $([[ -z "$token" ]] && echo "DALI_FISHTANK_TELEGRAM_TOKEN " )$([[ -z "$allowlist" ]] && echo "DALI_FISHTANK_TELEGRAM_ALLOWLIST")

Add lines:
  DALI_FISHTANK_TELEGRAM_ENABLED=1
  DALI_FISHTANK_TELEGRAM_TOKEN=<bot_token>
  DALI_FISHTANK_TELEGRAM_ALLOWLIST=<chat_id1>,<chat_id2>

Warning: Telegram 409 Conflict means another getUpdates poller is active.
Stop/disable competing pollers before enabling this service poller.
========================================================================
EOF
}

stop_legacy_services() {
  local units=("openclaw-mirror.service" "openclaw-telegram.service")
  for unit in "${units[@]}"; do
    if systemctl --user list-unit-files "$unit" >/dev/null 2>&1 || systemctl --user status "$unit" >/dev/null 2>&1; then
      log "stopping_legacy unit=$unit"
      systemctl --user disable --now "$unit" >/dev/null 2>&1 || true
      log "disabled_legacy unit=$unit"
      if [[ "$MASK_LEGACY" == "1" ]]; then
        systemctl --user mask "$unit" >/dev/null 2>&1 || true
        log "masked_legacy unit=$unit"
      fi
    fi
  done
}

log "bootstrap_venv"
bash "$ROOT_DIR/scripts/dali_fishtank_start.sh" bootstrap

log "install_or_update_unit"
bash "$ROOT_DIR/scripts/dali_fishtank_start.sh" install
systemctl --user daemon-reload

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: missing env file: $ENV_FILE" >&2
  exit 2
fi
check_telegram_env_actionable

if [[ "$STOP_LEGACY" == "1" ]]; then
  stop_legacy_services
else
  log "legacy_services_retained"
fi

if ! check_gpu_runtime_libs; then
  log "gpu_runtime_preflight_failed service_not_started"
  systemctl --user stop "$DALI_SERVICE" >/dev/null 2>&1 || true
  exit 3
fi

log "starting_dali_fishtank"
systemctl --user enable --now "$DALI_SERVICE"
systemctl --user enable --now "$WINDOW_START_TIMER" "$WINDOW_END_TIMER"
systemctl --user --no-pager --full status "$DALI_SERVICE" | sed -n '1,40p' || true
systemctl --user list-timers --all --no-pager | rg "dali-fishtank-window-(start|end)" || true

log "verification_checklist"
echo "CHECK_CMD systemctl --user status $DALI_SERVICE"
echo "CHECK_CMD systemctl --user list-timers --all --no-pager | rg 'dali-fishtank-window-(start|end)'"
echo "CHECK_CMD journalctl --user -u $DALI_SERVICE -n 80 --no-pager"
echo "CHECK_CMD python3 $ROOT_DIR/workspace/store/mirror_readers.py --json --pretty"
echo "CHECK_CMD ls -lah $ROOT_DIR/workspace/runtime"
echo "CHECK_CMD bash $ROOT_DIR/scripts/dali_fishtank_start.sh control status"
echo "CHECK_CMD telegram:/ping"
echo "OPTIONAL_GNOME_CMD gsettings get org.gnome.desktop.session idle-delay"
echo "OPTIONAL_GNOME_CMD gsettings set org.gnome.desktop.session idle-delay 900"
echo "OPTIONAL_GNOME_CMD gsettings get org.gnome.desktop.screensaver lock-enabled"
echo "OPTIONAL_GNOME_CMD gsettings set org.gnome.desktop.screensaver lock-enabled false"

echo "ROLLBACK_CMD systemctl --user stop $DALI_SERVICE"
echo "ROLLBACK_CMD systemctl --user disable $DALI_SERVICE"
echo "ROLLBACK_CMD systemctl --user disable --now $WINDOW_START_TIMER $WINDOW_END_TIMER"
echo "ROLLBACK_CMD systemctl --user enable --now openclaw-mirror.service"
echo "ROLLBACK_CMD systemctl --user enable --now openclaw-telegram.service"
