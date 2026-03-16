#!/usr/bin/env python3
from __future__ import annotations

import getpass
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.discord_surface.config import DEFAULT_BRIDGE_STATE_PATH, DEFAULT_PROJECTS_PATH, DEFAULT_SIM_PATH, DEFAULT_TASKS_PATH
from workspace.discord_surface.envfiles import write_env_file
from workspace.discord_surface.store import ensure_state_files


BOT_ENV_PATH = Path.home() / ".config" / "openclaw" / "discord-bot.env"
BRIDGE_ENV_PATH = Path.home() / ".config" / "openclaw" / "discord-bridge.env"


def _prompt(label: str, default: str = "", *, secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    if secret:
        value = getpass.getpass(f"{label}{suffix}: ").strip()
    else:
        value = input(f"{label}{suffix}: ").strip()
    return value or default


def main() -> int:
    token = _prompt("Discord bot token", secret=True)
    allowed_channels = _prompt("Allowed channel ids (comma-separated)")
    mutation_roles = _prompt("Mutation role ids (comma-separated, blank to require Manage Server/admin)")
    guild_ids = _prompt("Guild ids for command sync (comma-separated, optional)")
    tasks_path = Path(_prompt("Tasks JSON path", str(DEFAULT_TASKS_PATH))).expanduser()
    projects_path = Path(_prompt("Project inventory JSON path", str(DEFAULT_PROJECTS_PATH))).expanduser()
    sim_path = Path(_prompt("Sim JSON path", str(DEFAULT_SIM_PATH))).expanduser()
    bridge_state_path = Path(_prompt("Bridge state JSON path", str(DEFAULT_BRIDGE_STATE_PATH))).expanduser()
    health_services = _prompt("Health services (comma-separated systemd user units)", "openclaw-tool-mcp-qmd-http.service,openclaw-vllm.service")
    log_paths = _prompt("Log paths (comma-separated, optional)", "")
    ops_webhook = _prompt("Webhook URL for #ops-status", secret=True)
    sim_webhook = _prompt("Webhook URL for #sim-watch", secret=True)
    project_webhook = _prompt("Webhook URL for #project-intake", secret=True)

    bot_env = {
        "OPENCLAW_DISCORD_BOT_TOKEN": token,
        "OPENCLAW_DISCORD_ALLOWED_CHANNEL_IDS": allowed_channels,
        "OPENCLAW_DISCORD_MUTATION_ROLE_IDS": mutation_roles,
        "OPENCLAW_DISCORD_GUILD_IDS": guild_ids,
        "OPENCLAW_DISCORD_TASKS_JSON": str(tasks_path),
        "OPENCLAW_DISCORD_PROJECTS_JSON": str(projects_path),
        "OPENCLAW_DISCORD_SIM_JSON": str(sim_path),
        "OPENCLAW_DISCORD_BRIDGE_STATE_JSON": str(bridge_state_path),
        "OPENCLAW_DISCORD_HEALTH_SERVICES": health_services,
        "OPENCLAW_DISCORD_LOG_PATHS": log_paths,
    }
    bridge_env = {
        "OPENCLAW_DISCORD_TASKS_JSON": str(tasks_path),
        "OPENCLAW_DISCORD_PROJECTS_JSON": str(projects_path),
        "OPENCLAW_DISCORD_SIM_JSON": str(sim_path),
        "OPENCLAW_DISCORD_BRIDGE_STATE_JSON": str(bridge_state_path),
        "OPENCLAW_DISCORD_HEALTH_SERVICES": health_services,
        "OPENCLAW_DISCORD_LOG_PATHS": log_paths,
        "OPENCLAW_DISCORD_OPS_STATUS_WEBHOOK_URL": ops_webhook,
        "OPENCLAW_DISCORD_SIM_WATCH_WEBHOOK_URL": sim_webhook,
        "OPENCLAW_DISCORD_PROJECT_INTAKE_WEBHOOK_URL": project_webhook,
    }

    write_env_file(BOT_ENV_PATH, bot_env)
    write_env_file(BRIDGE_ENV_PATH, bridge_env)
    ensure_state_files(tasks_path, projects_path, bridge_state_path)

    print(f"wrote={BOT_ENV_PATH}")
    print(f"wrote={BRIDGE_ENV_PATH}")
    print(f"tasks_json={tasks_path}")
    print(f"projects_json={projects_path}")
    print(f"bridge_state_json={bridge_state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
