from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_ROOT = REPO_ROOT / "workspace" / "state_runtime" / "discord"
DEFAULT_TASKS_PATH = DEFAULT_STATE_ROOT / "tasks.json"
DEFAULT_PROJECTS_PATH = DEFAULT_STATE_ROOT / "project_inventory.json"
DEFAULT_BRIDGE_STATE_PATH = DEFAULT_STATE_ROOT / "bridge_delivery_state.json"
DEFAULT_SIM_PATH = REPO_ROOT / "reports" / "baseline_sim_metrics.json"


def _split_csv(text: str | None) -> list[str]:
    if not text:
        return []
    return [item.strip() for item in str(text).split(",") if item.strip()]


def _split_int_csv(text: str | None) -> set[int]:
    result: set[int] = set()
    for item in _split_csv(text):
        try:
            result.add(int(item))
        except ValueError:
            continue
    return result


def _path_from_env(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser()


@dataclass(frozen=True)
class DiscordBotConfig:
    token: str
    allowed_channel_ids: set[int]
    mutation_role_ids: set[int]
    guild_ids: set[int]
    tasks_path: Path
    projects_path: Path
    sim_path: Path
    bridge_state_path: Path
    health_services: list[str]
    log_paths: list[Path]

    @classmethod
    def from_env(cls) -> "DiscordBotConfig":
        return cls(
            token=os.environ.get("OPENCLAW_DISCORD_BOT_TOKEN", "").strip(),
            allowed_channel_ids=_split_int_csv(os.environ.get("OPENCLAW_DISCORD_ALLOWED_CHANNEL_IDS")),
            mutation_role_ids=_split_int_csv(os.environ.get("OPENCLAW_DISCORD_MUTATION_ROLE_IDS")),
            guild_ids=_split_int_csv(os.environ.get("OPENCLAW_DISCORD_GUILD_IDS")),
            tasks_path=_path_from_env("OPENCLAW_DISCORD_TASKS_JSON", DEFAULT_TASKS_PATH),
            projects_path=_path_from_env("OPENCLAW_DISCORD_PROJECTS_JSON", DEFAULT_PROJECTS_PATH),
            sim_path=_path_from_env("OPENCLAW_DISCORD_SIM_JSON", DEFAULT_SIM_PATH),
            bridge_state_path=_path_from_env("OPENCLAW_DISCORD_BRIDGE_STATE_JSON", DEFAULT_BRIDGE_STATE_PATH),
            health_services=_split_csv(os.environ.get("OPENCLAW_DISCORD_HEALTH_SERVICES")),
            log_paths=[Path(item).expanduser() for item in _split_csv(os.environ.get("OPENCLAW_DISCORD_LOG_PATHS"))],
        )


@dataclass(frozen=True)
class DiscordBridgeConfig:
    tasks_path: Path
    projects_path: Path
    sim_path: Path
    bridge_state_path: Path
    health_services: list[str]
    log_paths: list[Path]
    ops_status_webhook_url: str
    sim_watch_webhook_url: str
    project_intake_webhook_url: str

    @classmethod
    def from_env(cls) -> "DiscordBridgeConfig":
        return cls(
            tasks_path=_path_from_env("OPENCLAW_DISCORD_TASKS_JSON", DEFAULT_TASKS_PATH),
            projects_path=_path_from_env("OPENCLAW_DISCORD_PROJECTS_JSON", DEFAULT_PROJECTS_PATH),
            sim_path=_path_from_env("OPENCLAW_DISCORD_SIM_JSON", DEFAULT_SIM_PATH),
            bridge_state_path=_path_from_env("OPENCLAW_DISCORD_BRIDGE_STATE_JSON", DEFAULT_BRIDGE_STATE_PATH),
            health_services=_split_csv(os.environ.get("OPENCLAW_DISCORD_HEALTH_SERVICES")),
            log_paths=[Path(item).expanduser() for item in _split_csv(os.environ.get("OPENCLAW_DISCORD_LOG_PATHS"))],
            ops_status_webhook_url=os.environ.get("OPENCLAW_DISCORD_OPS_STATUS_WEBHOOK_URL", "").strip(),
            sim_watch_webhook_url=os.environ.get("OPENCLAW_DISCORD_SIM_WATCH_WEBHOOK_URL", "").strip(),
            project_intake_webhook_url=os.environ.get("OPENCLAW_DISCORD_PROJECT_INTAKE_WEBHOOK_URL", "").strip(),
        )
