#!/usr/bin/env python3
"""Sync the current OpenClaw Telegram main-session transcript into memory."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.scripts.telegram_memory_backfill import (  # type: ignore
    ENV_FILE,
    backfill_rows,
    load_env_file,
    load_rows,
    parse_csv_set,
)

SESSIONS_INDEX = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"


def resolve_transcript_path() -> Path | None:
    if not SESSIONS_INDEX.exists():
        return None
    try:
        payload = json.loads(SESSIONS_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    main = payload.get("agent:main:main")
    if not isinstance(main, dict):
        return None
    transcript = str(main.get("transcriptPath") or main.get("sessionFile") or "").strip()
    if not transcript:
        return None
    path = Path(transcript)
    return path if path.exists() else None


def main() -> int:
    load_env_file(ENV_FILE)
    transcript_path = resolve_transcript_path()
    if transcript_path is None:
        print(json.dumps({"status": "no_transcript"}, indent=2))
        return 0
    rows = load_rows(transcript_path)
    summary = backfill_rows(
        rows,
        allowed_chat_ids={chunk.strip() for chunk in os.environ.get("OPENCLAW_TELEGRAM_MEMORY_CHAT_IDS", "").split(",") if chunk.strip()},
        self_ids={chunk.strip() for chunk in os.environ.get("OPENCLAW_TELEGRAM_MEMORY_SELF_IDS", "").split(",") if chunk.strip()},
        self_names=parse_csv_set(os.environ.get("OPENCLAW_TELEGRAM_MEMORY_SELF_NAMES", "jeebs,j33bs,heath,heath yeager")),
        assistant_names=parse_csv_set(os.environ.get("OPENCLAW_TELEGRAM_MEMORY_ASSISTANT_NAMES", "dali,c_lawd,openclaw")),
        agent_scope=os.environ.get("OPENCLAW_TELEGRAM_MEMORY_AGENT_SCOPE", "main").strip() or "main",
    )
    summary["status"] = "ok"
    summary["transcript_path"] = str(transcript_path)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
