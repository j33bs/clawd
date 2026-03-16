#!/usr/bin/env python3
"""Deprecated transcript sync stub.

Telegram memory should come from real Telegram turns plus gateway replies, not
from replaying `agent:main:main` prompt transcripts into memory.
"""

from __future__ import annotations

import json


def main() -> int:
    print(
        json.dumps(
            {
                "status": "disabled",
                "reason": "transcript_sync_deprecated",
                "detail": "Use openclaw-telegram-memory.service for user turns and gateway reply ingest for assistant turns.",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
