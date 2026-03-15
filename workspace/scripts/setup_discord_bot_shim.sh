#!/usr/bin/env bash
set -euo pipefail

ENV_DIR="${HOME}/.config/openclaw"
ENV_FILE="${ENV_DIR}/discord-bot.env"

mkdir -p "${ENV_DIR}"
chmod 700 "${ENV_DIR}"

read -r -p "Discord application ID (optional but recommended): " APP_ID
read -r -p "Discord guild/server ID (optional, enables fast guild sync): " GUILD_ID
read -r -p "Bot status text [watching Dali]: " STATUS_TEXT
STATUS_TEXT="${STATUS_TEXT:-watching Dali}"
read -r -p "Allowed channel IDs (comma-separated, optional): " ALLOWED_CHANNEL_IDS
read -r -p "Task mutation role IDs (comma-separated, optional): " MUTATION_ROLE_IDS
read -r -s -p "Discord bot token: " BOT_TOKEN
echo

cat > "${ENV_FILE}" <<EOF
OPENCLAW_DISCORD_BOT_TOKEN=${BOT_TOKEN}
OPENCLAW_DISCORD_APP_ID=${APP_ID}
OPENCLAW_DISCORD_GUILD_ID=${GUILD_ID}
OPENCLAW_DISCORD_BOT_STATUS=${STATUS_TEXT}
OPENCLAW_DISCORD_ALLOWED_CHANNEL_IDS=${ALLOWED_CHANNEL_IDS}
OPENCLAW_DISCORD_MUTATION_ROLE_IDS=${MUTATION_ROLE_IDS}
EOF

chmod 600 "${ENV_FILE}"

cat <<MSG
Wrote ${ENV_FILE}

Next steps:
1. Ensure the Discord bot venv exists and has discord.py installed.
2. Install the user service:
   install -m 644 ~/src/clawd/workspace/systemd/openclaw-discord-bot.service ~/.config/systemd/user/openclaw-discord-bot.service
3. Reload systemd:
   systemctl --user daemon-reload
4. Start the bot:
   systemctl --user enable --now openclaw-discord-bot.service

If OPENCLAW_DISCORD_GUILD_ID is set, slash commands will sync to that guild immediately.
MSG
