#!/usr/bin/env python3
"""Render or deliver Discord bridge payloads from canonical local state."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
for path in (SOURCE_UI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api.discord_bridge import post_bridge_webhooks, render_bridge_state  # type: ignore
from api.portfolio import portfolio_payload  # type: ignore
from api.task_store import load_tasks  # type: ignore

ENV_FILE = Path.home() / ".config" / "openclaw" / "discord-bridge.env"


def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def build_payload() -> dict:
    portfolio = portfolio_payload()
    tasks = load_tasks()
    return render_bridge_state(portfolio, tasks)


def main() -> int:
    load_env_file()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("preview", "render-status", "post-webhooks"),
        nargs="?",
        default="preview",
        help="Bridge action to run.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full JSON payload instead of a compact summary.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force webhook delivery even when the rendered message is unchanged.",
    )
    args = parser.parse_args()

    payload = build_payload()

    if args.command == "post-webhooks":
        force = args.force or os.environ.get("OPENCLAW_DISCORD_BRIDGE_FORCE", "0") == "1"
        results = post_bridge_webhooks(payload, force=force)
        print(json.dumps({"results": results}, indent=2))
        return 0

    if args.command == "render-status" or args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"status={payload.get('status')} enabled={payload.get('enabled')} dry_run={payload.get('dry_run')}")
    for channel in payload.get("channels", []):
        label = channel.get("label") or channel.get("id")
        print(f"[{label}] enabled={channel.get('enabled')} webhook={channel.get('has_webhook')}")
        print(channel.get("preview", ""))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
