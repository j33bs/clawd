#!/usr/bin/env python3
"""Generate a three-year world-better roadmap snapshot for Source."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
ROADMAP_ROOT = REPO_ROOT / "workspace" / "roadmaps"
ROADMAP_PATH = ROADMAP_ROOT / "source-world-better-roadmap.md"

if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api.portfolio import portfolio_payload  # noqa: E402
from api.world_better import build_three_year_roadmap_markdown  # noqa: E402


def main() -> int:
    ROADMAP_ROOT.mkdir(parents=True, exist_ok=True)
    portfolio = portfolio_payload()
    world_better = portfolio.get("world_better") if isinstance(portfolio, dict) else {}
    markdown = build_three_year_roadmap_markdown(world_better or {})
    header = f"<!-- generated_at: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} -->\n"
    ROADMAP_PATH.write_text(header + markdown, encoding="utf-8")
    print(ROADMAP_PATH.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
