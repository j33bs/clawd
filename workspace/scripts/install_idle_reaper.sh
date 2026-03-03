#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p "$HOME/.config/systemd/user"
install -m 0644 workspace/systemd/openclaw-idle-reaper.service "$HOME/.config/systemd/user/"
install -m 0644 workspace/systemd/openclaw-idle-reaper.timer "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now openclaw-idle-reaper.timer
systemctl --user list-timers --all | rg 'openclaw-idle-reaper' || true
echo "Installed idle reaper timer."
