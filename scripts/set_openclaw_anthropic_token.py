#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTH_FILE = REPO_ROOT / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def load_or_init(path: Path) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"invalid_auth_profiles_json:{path}") from exc
        if isinstance(data, dict):
            return data
    return {
        "version": 1,
        "profiles": {},
        "order": {},
        "lastGood": {},
        "usageStats": {},
    }


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.bak-{utc_stamp()}")
    backup.write_bytes(path.read_bytes())
    return backup


def update_anthropic_profile(data: dict, *, profile_id: str, token: str, prioritize: bool) -> dict:
    profiles = data.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("invalid_profiles_map")
    profiles[profile_id] = {
        "provider": "anthropic",
        "type": "token",
        "token": token,
    }

    if prioritize:
        order = data.setdefault("order", {})
        if not isinstance(order, dict):
            raise ValueError("invalid_order_map")
        current = order.get("anthropic")
        if not isinstance(current, list):
            current = []
        deduped = [profile_id]
        for item in current:
            if item != profile_id and isinstance(item, str):
                deduped.append(item)
        order["anthropic"] = deduped
    return data


def write_auth_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_token(args: argparse.Namespace) -> str:
    if args.stdin:
        token = sys.stdin.read().strip()
    else:
        prompt = f"Anthropic token for {args.profile_id}: "
        token = getpass.getpass(prompt).strip()
    if not token:
        raise ValueError("empty_token")
    return token


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prompt for an Anthropic token and store it in OpenClaw auth-profiles.json.")
    parser.add_argument("--auth-file", default=str(DEFAULT_AUTH_FILE), help="Target auth-profiles.json path.")
    parser.add_argument("--profile-id", default="anthropic:manual", help="Anthropic profile id to write.")
    parser.add_argument("--stdin", action="store_true", help="Read the token from stdin instead of hidden prompt.")
    parser.add_argument(
        "--no-prioritize",
        action="store_true",
        help="Do not move this profile to the front of the anthropic auth order.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    auth_file = Path(args.auth_file).expanduser().resolve()
    token = read_token(args)
    data = load_or_init(auth_file)
    backup = backup_file(auth_file)
    update_anthropic_profile(
        data,
        profile_id=str(args.profile_id),
        token=token,
        prioritize=not args.no_prioritize,
    )
    write_auth_file(auth_file, data)

    summary = {
        "status": "ok",
        "auth_file": str(auth_file),
        "backup": str(backup) if backup else None,
        "profile_id": str(args.profile_id),
        "prioritized": not args.no_prioritize,
    }
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
