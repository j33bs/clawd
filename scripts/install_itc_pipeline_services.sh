#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
OPENCLAW_CONFIG_DIR="${HOME}/.config/openclaw"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"

mkdir -p "$SYSTEMD_USER_DIR" "$OPENCLAW_CONFIG_DIR" "${HOME}/.local/state/openclaw"

install -m 0644 "$ROOT_DIR/workspace/systemd/openclaw-vllm.service" "$SYSTEMD_USER_DIR/openclaw-vllm.service"
install -m 0644 "$ROOT_DIR/workspace/systemd/openclaw-itc-cycle.service" "$SYSTEMD_USER_DIR/openclaw-itc-cycle.service"
install -m 0644 "$ROOT_DIR/workspace/systemd/openclaw-itc-cycle.timer" "$SYSTEMD_USER_DIR/openclaw-itc-cycle.timer"
install -m 0644 "$ROOT_DIR/workspace/systemd/openclaw-itc-telegram.service" "$SYSTEMD_USER_DIR/openclaw-itc-telegram.service"
install -m 0644 "$ROOT_DIR/workspace/systemd/openclaw-market-stream.service" "$SYSTEMD_USER_DIR/openclaw-market-stream.service"

if [[ ! -f "$OPENCLAW_CONFIG_DIR/vllm-assistant.env" ]]; then
  cat > "$OPENCLAW_CONFIG_DIR/vllm-assistant.env" <<'EOF'
OPENCLAW_VLLM_ASSISTANT_PORT=8001
OPENCLAW_VLLM_ASSISTANT_GPU_MEMORY_UTILIZATION=0.85
OPENCLAW_VLLM_ASSISTANT_QUANTIZATION=awq_marlin
EOF
fi

if [[ ! -f "$OPENCLAW_CONFIG_DIR/itc-cycle.env" ]]; then
  cat > "$OPENCLAW_CONFIG_DIR/itc-cycle.env" <<'EOF'
OPENCLAW_ITC_MARKET_LIMIT=300
OPENCLAW_ITC_MAX_LLM=80
OPENCLAW_ITC_SKIP_MARKET=1
# OPENCLAW_ITC_MODEL=local-assistant
# OPENCLAW_ITC_SIM_ID=SIM_A
# OPENCLAW_ITC_SYMBOLS=BTCUSDT,ETHUSDT
EOF
fi

if [[ ! -f "$OPENCLAW_CONFIG_DIR/itc-telegram.env" ]]; then
  cat > "$OPENCLAW_CONFIG_DIR/itc-telegram.env" <<'EOF'
OPENCLAW_ITC_TELEGRAM_BACKFILL=50
# OPENCLAW_ITC_TELEGRAM_DRY_RUN=1
EOF
fi

if [[ ! -f "$OPENCLAW_CONFIG_DIR/market-stream.env" ]]; then
  cat > "$OPENCLAW_CONFIG_DIR/market-stream.env" <<'EOF'
OPENCLAW_MARKET_STREAM_BACKFILL_LIMIT=300
OPENCLAW_MARKET_STREAM_TICK_LOOKBACK_MS=300000
OPENCLAW_MARKET_STREAM_FLUSH_INTERVAL_SEC=2.0
OPENCLAW_MARKET_STREAM_RECONNECT_SEC=5.0
# OPENCLAW_MARKET_STREAM_SYMBOLS=BTCUSDT,ETHUSDT
EOF
fi

systemctl --user daemon-reload
systemctl --user enable openclaw-vllm.service >/dev/null
systemctl --user enable openclaw-itc-cycle.timer >/dev/null
systemctl --user enable openclaw-itc-telegram.service >/dev/null
systemctl --user enable openclaw-market-stream.service >/dev/null

echo "CHECK_OK installed openclaw-vllm.service openclaw-itc-cycle.service openclaw-itc-cycle.timer openclaw-itc-telegram.service openclaw-market-stream.service"
echo "CHECK_CMD systemctl --user restart openclaw-vllm.service"
echo "CHECK_CMD systemctl --user restart openclaw-itc-telegram.service"
echo "CHECK_CMD systemctl --user restart openclaw-market-stream.service"
echo "CHECK_CMD systemctl --user start openclaw-itc-cycle.service"
echo "CHECK_CMD systemctl --user enable --now openclaw-itc-cycle.timer"
echo "CHECK_CMD journalctl --user -u openclaw-vllm.service -n 80 --no-pager"
echo "CHECK_CMD journalctl --user -u openclaw-itc-telegram.service -n 80 --no-pager"
echo "CHECK_CMD journalctl --user -u openclaw-market-stream.service -n 80 --no-pager"
echo "CHECK_CMD journalctl --user -u openclaw-itc-cycle.service -n 80 --no-pager"
