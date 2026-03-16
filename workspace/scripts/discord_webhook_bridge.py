#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.discord_surface.bridge_runtime import run_bridge
from workspace.discord_surface.config import DiscordBridgeConfig
from workspace.discord_surface.envfiles import load_env_file
from workspace.discord_surface.store import ensure_state_files


DEFAULT_ENV_FILE = Path.home() / ".config" / "openclaw" / "discord-bridge.env"


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw Discord webhook bridge")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    args = parser.parse_args()
    for key, value in load_env_file(Path(args.env_file)).items():
        os.environ.setdefault(key, value)
    config = DiscordBridgeConfig.from_env()
    ensure_state_files(config.tasks_path, config.projects_path, config.bridge_state_path)
    for result in run_bridge(config):
        print(f"{result.key} status={result.status} detail={result.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
