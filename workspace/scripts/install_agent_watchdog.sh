#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SRC_DIR="${ROOT}/workspace/systemd"
DST_DIR="${HOME}/.config/systemd/user"

mkdir -p "${DST_DIR}"

install -m 0644 "${SRC_DIR}/openclaw-agent-watchdog.service" "${DST_DIR}/openclaw-agent-watchdog.service"
install -m 0644 "${SRC_DIR}/openclaw-agent-watchdog.timer" "${DST_DIR}/openclaw-agent-watchdog.timer"

systemctl --user daemon-reload
systemctl --user enable --now openclaw-agent-watchdog.timer
systemctl --user start openclaw-agent-watchdog.service || true

printf 'installed: %s\n' "${DST_DIR}/openclaw-agent-watchdog.service"
printf 'installed: %s\n' "${DST_DIR}/openclaw-agent-watchdog.timer"
systemctl --user status openclaw-agent-watchdog.timer --no-pager || true
