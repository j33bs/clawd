#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p "$HOME/.config/systemd/user"
install -m 0644 workspace/systemd/openclaw-contract-manager.service "$HOME/.config/systemd/user/"
install -m 0644 workspace/systemd/openclaw-contract-manager.timer "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now openclaw-contract-manager.timer
systemctl --user list-timers --all | rg 'openclaw-contract-manager' || true
echo "Installed contract manager timer."
