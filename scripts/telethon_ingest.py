#!/usr/bin/env python3
"""
Compatibility wrapper for the canonical ITC Telethon reader.

This preserves the old `scripts/telethon_ingest.py` entrypoint and legacy
environment variable names, but routes all ingestion through
`workspace.itc_pipeline.telegram_reader_telethon` so Telegram data reaches the
dedupe boundary, classifier feed, and normalized ITC artifact contract.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILES = (
    REPO_ROOT / "secrets.env",
    Path.home() / ".openclaw" / "secrets.env",
)
LEGACY_ENV_MAP = {
    "TELETHON_API_ID": "TG_API_ID",
    "TELETHON_API_HASH": "TG_API_HASH",
    "TELETHON_PHONE": "TG_PHONE",
    "TELETHON_SESSION_PATH": "TG_SESSION_PATH",
}


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def bootstrap_environment() -> None:
    for env_file in DEFAULT_ENV_FILES:
        _load_env_file(env_file)
    for legacy_key, canonical_key in LEGACY_ENV_MAP.items():
        if not os.environ.get(canonical_key) and os.environ.get(legacy_key):
            os.environ[canonical_key] = os.environ[legacy_key]


def _load_reader_module():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("workspace.itc_pipeline.telegram_reader_telethon")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Legacy Telethon ITC ingester compatibility wrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/telethon_ingest.py --auth
  # Missing API ID / hash / phone will be prompted interactively and can be saved
  python scripts/telethon_ingest.py --auth --reconfigure
  python scripts/telethon_ingest.py --once --backfill 100
  python scripts/telethon_ingest.py --backfill 100
        """,
    )
    parser.add_argument("--auth", action="store_true", help="Authenticate the Telethon session")
    parser.add_argument("--reconfigure", action="store_true", help="Prompt for Telegram credentials even if saved")
    parser.add_argument("--once", action="store_true", help="Backfill then exit")
    parser.add_argument("--backfill", type=int, default=100, help="Messages per allowed chat to backfill")
    parser.add_argument("--dry-run", action="store_true", help="Log accepted messages without persisting them")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    bootstrap_environment()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    reader = _load_reader_module()
    if args.auth:
        asyncio.run(reader.authenticate(force_prompt=args.reconfigure))
        return 0

    asyncio.run(
        reader.run_ingestion(
            dry_run=args.dry_run,
            backfill_limit=args.backfill,
            exit_after_backfill=args.once,
            force_prompt=args.reconfigure,
        )
    )
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
