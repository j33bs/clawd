#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p "$HOME/.config/systemd/user"
install -m 0644 "$ROOT/workspace/systemd/openclaw-heavy-worker.service" "$HOME/.config/systemd/user/"
install -m 0644 "$ROOT/workspace/systemd/openclaw-heavy-worker.timer" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now openclaw-heavy-worker.timer
systemctl --user list-timers --all | rg 'openclaw-heavy-worker' || true
echo "Installed openclaw-heavy-worker.timer"
