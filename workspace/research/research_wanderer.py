#!/usr/bin/env python3
"""Compatibility wrapper for workspace/scripts/research_wanderer.py."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from research_wanderer import main  # type: ignore  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
