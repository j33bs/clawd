#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

mkdir -p "$HOME/.config/systemd/user"
mkdir -p "$HOME/.local/state/openclaw/tools"
mkdir -p "$HOME/.config/openclaw"

# Install units (copy repo-tracked units into systemd user dir)
install -m 0644 workspace/systemd/openclaw-tool-coder-vllm-models.service "$HOME/.config/systemd/user/"
install -m 0644 workspace/systemd/openclaw-tool-mcp-qmd-http.service "$HOME/.config/systemd/user/"
install -m 0644 workspace/systemd/openclaw-tool-ain-phi.service "$HOME/.config/systemd/user/"

systemctl --user daemon-reload

# Enable and start (best-effort: services may fail if CMD env not configured)
systemctl --user enable --now openclaw-tool-coder-vllm-models.service || true
systemctl --user enable --now openclaw-tool-mcp-qmd-http.service || true
systemctl --user enable --now openclaw-tool-ain-phi.service || true

systemctl --user status openclaw-tool-coder-vllm-models.service --no-pager || true
systemctl --user status openclaw-tool-mcp-qmd-http.service --no-pager || true
systemctl --user status openclaw-tool-ain-phi.service --no-pager || true

echo
echo "Installed. If a service fails, set commands in:"
echo "  ~/.config/openclaw/tools.env"
echo
echo "Example:"
echo "  export OPENCLAW_TOOL_CMD_CODER_VLLM_MODELS='python3 -m vllm.entrypoints.openai.api_server --host 127.0.0.1 --port 8002 ...'"
echo "  export OPENCLAW_TOOL_CMD_MCP_QMD_HTTP='node ~/src/clawd/scripts/system2_http_edge.js --port 8181 ...'"
echo "  export OPENCLAW_TOOL_CMD_AIN_PHI='...bind 127.0.0.1:18990...'"
