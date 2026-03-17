#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

mkdir -p "$HOME/.config/systemd/user"
mkdir -p "$HOME/.local/state/openclaw/tools"
mkdir -p "$HOME/.local/state/openclaw"
mkdir -p "$HOME/.config/openclaw"

# Install units (copy repo-tracked units into systemd user dir)
install -m 0644 workspace/systemd/openclaw-tool-coder-vllm-models.service "$HOME/.config/systemd/user/"
install -m 0644 workspace/systemd/openclaw-tool-mcp-qmd-http.service "$HOME/.config/systemd/user/"
install -m 0644 workspace/systemd/openclaw-source-ui-local.service "$HOME/.config/systemd/user/"
install -m 0644 workspace/systemd/openclaw-fullscreen-idle-inhibit.service "$HOME/.config/systemd/user/"
ln -sfn openclaw-source-ui-local.service "$HOME/.config/systemd/user/openclaw-tool-ain-phi.service"

systemctl --user daemon-reload

# Enable and start (best-effort: services may fail if CMD env not configured)
systemctl --user enable --now openclaw-tool-coder-vllm-models.service || true
systemctl --user enable --now openclaw-tool-mcp-qmd-http.service || true
systemctl --user enable --now openclaw-source-ui-local.service || true
systemctl --user enable --now openclaw-fullscreen-idle-inhibit.service || true

systemctl --user status openclaw-tool-coder-vllm-models.service --no-pager || true
systemctl --user status openclaw-tool-mcp-qmd-http.service --no-pager || true
systemctl --user status openclaw-source-ui-local.service --no-pager || true
systemctl --user status openclaw-fullscreen-idle-inhibit.service --no-pager || true

echo
echo "Installed. If a service fails, set commands in:"
echo "  ~/.config/openclaw/tools.env"
echo
echo "Example:"
echo "  export OPENCLAW_TOOL_CMD_CODER_VLLM_MODELS='python3 -m vllm.entrypoints.openai.api_server --host 127.0.0.1 --port 8002 ...'"
echo "  export OPENCLAW_TOOL_CMD_MCP_QMD_HTTP='node ~/src/clawd/scripts/system2_http_edge.js --port 8181 ...'"
echo "Local Source UI is managed by openclaw-source-ui-local.service."
echo "Fullscreen idle inhibition is managed by openclaw-fullscreen-idle-inhibit.service."
