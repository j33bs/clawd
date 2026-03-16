#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = REPO_ROOT / "workspace" / "state_runtime" / "twitter_api.env"


ENV_FIELDS = (
    ("bearer_token", "X_BEARER_TOKEN", "Bearer token", False),
    ("api_key", "X_API_KEY", "API key / consumer key", False),
    ("api_secret", "X_API_SECRET", "API secret / consumer secret", False),
    ("access_token", "X_ACCESS_TOKEN", "Access token", False),
    ("access_token_secret", "X_ACCESS_TOKEN_SECRET", "Access token secret", False),
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.bak-{utc_stamp()}")
    backup.write_bytes(path.read_bytes())
    return backup


def prompt_secret(label: str, *, required: bool) -> str | None:
    value = getpass.getpass(f"{label}{' (required)' if required else ' (optional, Enter to skip)'}: ").strip()
    if value:
        return value
    if required:
        raise ValueError(f"missing_required:{label}")
    return None


def collect_values(args: argparse.Namespace) -> dict[str, str]:
    values: dict[str, str] = {}
    for field_name, env_name, label, required in ENV_FIELDS:
        cli_value = getattr(args, field_name)
        if cli_value:
            values[env_name] = cli_value.strip()
            continue
        prompted = prompt_secret(label, required=required)
        if prompted:
            values[env_name] = prompted
    return values


def render_env(values: dict[str, str]) -> str:
    lines = [
        "# Local X/Twitter API credentials",
        "# Source this file before running scraping tools.",
    ]
    for _, env_name, _, _ in ENV_FIELDS:
        if env_name in values:
            lines.append(f"{env_name}={values[env_name]}")
    return "\n".join(lines) + "\n"


def write_env_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_env(values), encoding="utf-8")
    path.chmod(0o600)


def present_fields(values: dict[str, str]) -> list[str]:
    ordered: list[str] = []
    for _, env_name, _, _ in ENV_FIELDS:
        if env_name in values:
            ordered.append(env_name)
    return ordered


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prompt for X/Twitter API credentials and store them in a local env file.",
    )
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Target env file path.")
    parser.add_argument("--bearer-token", help="X bearer token.")
    parser.add_argument("--api-key", help="X API key.")
    parser.add_argument("--api-secret", help="X API secret.")
    parser.add_argument("--consumer-key", help="Alias for --api-key.")
    parser.add_argument("--consumer-secret", help="Alias for --api-secret.")
    parser.add_argument("--access-token", help="X access token.")
    parser.add_argument("--access-token-secret", help="X access token secret.")
    return parser


def validate_values(values: dict[str, str]) -> None:
    has_bearer = bool(values.get("X_BEARER_TOKEN"))
    has_oauth1 = all(
        values.get(key)
        for key in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    )
    if not has_bearer and not has_oauth1:
        raise ValueError("need_bearer_or_full_oauth1_credentials")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    env_file = Path(args.env_file).expanduser().resolve()

    if getattr(args, "consumer_key", None) and not getattr(args, "api_key", None):
        args.api_key = args.consumer_key
    if getattr(args, "consumer_secret", None) and not getattr(args, "api_secret", None):
        args.api_secret = args.consumer_secret

    values = collect_values(args)
    validate_values(values)
    backup = backup_file(env_file)
    write_env_file(env_file, values)

    print(f"status=ok")
    print(f"env_file={env_file}")
    print(f"backup={backup if backup else ''}")
    print(f"fields={','.join(present_fields(values))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
