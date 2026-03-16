#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="dali-fishtank.service"
SERVICE_DEST="$HOME/.config/systemd/user/$SERVICE_NAME"

systemctl --user disable --now "$SERVICE_NAME" 2>/dev/null || true
rm -f "$SERVICE_DEST"
systemctl --user daemon-reload

echo "CHECK_OK dali_fishtank_service_disabled unit=$SERVICE_NAME"
echo "CHECK_INFO to_reenable=bash scripts/dali_fishtank_start.sh start"
