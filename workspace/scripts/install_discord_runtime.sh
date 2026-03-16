#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VENV_PATH="$HOME/.local/share/openclaw/venvs/discord-bot"
mkdir -p "$HOME/.config/systemd/user" "$HOME/.config/openclaw" "$HOME/.local/state/openclaw/discord"

python3 -m venv "$VENV_PATH"
"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install -r "$ROOT/workspace/discord_surface/requirements.txt"

install -m 0644 "$ROOT/workspace/systemd/openclaw-discord-bot.service" "$HOME/.config/systemd/user/"
install -m 0644 "$ROOT/workspace/systemd/openclaw-discord-bridge.service" "$HOME/.config/systemd/user/"
install -m 0644 "$ROOT/workspace/systemd/openclaw-discord-bridge.timer" "$HOME/.config/systemd/user/"

systemctl --user daemon-reload
systemctl --user enable --now openclaw-discord-bot.service || true
systemctl --user enable --now openclaw-discord-bridge.timer || true

echo "Discord runtime installed."
echo "Venv: $VENV_PATH"
echo "Next: python3 $ROOT/workspace/scripts/setup_discord_env.py"
