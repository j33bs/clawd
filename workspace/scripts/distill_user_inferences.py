#!/usr/bin/env python3
"""Distill durable user inferences from local Discord/Telegram memory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
for path in (SOURCE_UI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api.user_inference import distill_user_inferences, sync_preference_packet_to_workspaces  # type: ignore


def main() -> int:
    result = distill_user_inferences()
    result["workspace_sync"] = sync_preference_packet_to_workspaces()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
