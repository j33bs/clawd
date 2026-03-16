#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${HOME}/.config/openclaw/discord-bot.env"
VENV_PYTHON="${HOME}/src/clawd/.venv-discord-bot/bin/python"

if [[ -f "${ENV_FILE}" ]]; then
  while IFS= read -r line; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "${line}" || "${line}" == \#* || "${line}" != *=* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    export "${key}"="${value}"
  done < "${ENV_FILE}"
fi

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Missing Discord bot venv: ${VENV_PYTHON}" >&2
  echo "Create it with: python3 -m venv ~/.venv-discord-bot or /home/jeebs/src/clawd/.venv-discord-bot and install discord.py" >&2
  exit 127
fi

cd "${HOME}/src/clawd"
exec "${VENV_PYTHON}" workspace/scripts/discord_bot.py
