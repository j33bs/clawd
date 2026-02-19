#!/usr/bin/env python3
"""Explicit temporal beacon touch/update command (no daemon)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tacti_cr.temporal_watchdog import update_beacon  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(update_beacon(), ensure_ascii=True))
