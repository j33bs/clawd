from __future__ import annotations

from dataclasses import dataclass

from .bridge import load_delivery_state, post_webhook, record_delivery, should_skip_delivery
from .config import DiscordBridgeConfig
from .snapshots import (
    build_ops_snapshot,
    build_project_snapshot,
    build_sim_snapshot,
    format_ops_message,
    format_project_message,
    format_sim_message,
)
from .store import ensure_state_files


@dataclass(frozen=True)
class BridgeResult:
    key: str
    status: str
    detail: str


def run_bridge(config: DiscordBridgeConfig) -> list[BridgeResult]:
    ensure_state_files(config.tasks_path, config.projects_path, config.bridge_state_path)
    state = load_delivery_state(config.bridge_state_path)
    outputs = {
        "ops_status": (
            config.ops_status_webhook_url,
            format_ops_message(
                build_ops_snapshot(
                    tasks_path=config.tasks_path,
                    projects_path=config.projects_path,
                    sim_path=config.sim_path,
                    health_services=config.health_services,
                    log_paths=config.log_paths,
                )
            ),
        ),
        "sim_watch": (config.sim_watch_webhook_url, format_sim_message(build_sim_snapshot(config.sim_path))),
        "project_intake": (
            config.project_intake_webhook_url,
            format_project_message(build_project_snapshot(config.tasks_path, config.projects_path)),
        ),
    }
    results: list[BridgeResult] = []
    for key, (url, content) in outputs.items():
        if not url:
            results.append(BridgeResult(key=key, status="skipped", detail="missing_webhook"))
            continue
        if should_skip_delivery(state, key, content):
            results.append(BridgeResult(key=key, status="skipped", detail="unchanged"))
            continue
        response = post_webhook(url, content)
        response.raise_for_status()
        record_delivery(config.bridge_state_path, state, key, content, status="ok")
        results.append(BridgeResult(key=key, status="ok", detail=f"http_{response.status_code}"))
    return results
