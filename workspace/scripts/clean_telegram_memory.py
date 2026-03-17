#!/usr/bin/env python3
"""Back up and sanitize the Telegram memory archive."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
for path in (SOURCE_UI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api.telegram_memory import (  # type: ignore
    TELEGRAM_MEMORY_PATH,
    TELEGRAM_MEMORY_STATE_PATH,
    sanitize_telegram_memory_archive,
)


def _backup_path(target: Path, backup_dir: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return backup_dir / f"{target.name}.{timestamp}.bak"


def _copy_if_exists(source: Path, backup_dir: Path) -> list[str]:
    if not source.exists():
        return []
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = _backup_path(source, backup_dir)
    shutil.copy2(source, destination)
    return [str(destination)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backup-dir",
        default=str(REPO_ROOT / "workspace" / "runtime" / "backups" / "telegram-memory"),
        help="Directory for pre-clean backups.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backup_dir = Path(args.backup_dir).expanduser().resolve()
    backups = []
    backups.extend(_copy_if_exists(TELEGRAM_MEMORY_PATH, backup_dir))
    backups.extend(_copy_if_exists(TELEGRAM_MEMORY_STATE_PATH, backup_dir))
    summary = sanitize_telegram_memory_archive()
    summary["backup_paths"] = backups
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
