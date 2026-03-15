#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${HOME}/.config/openclaw/discord-bridge.env"
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

CMD="${OPENCLAW_DISCORD_BRIDGE_COMMAND:-render-status}"
REPO_ROOT="${HOME}/src/clawd"

cd "${REPO_ROOT}"
exec /usr/bin/env python3 workspace/scripts/discord_project_bridge.py "${CMD}"
