#!/usr/bin/env python3
"""Write or preview the periodic strategy review for AU paper lanes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
for path in (SOURCE_UI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api.portfolio import _load_finance_brain, _load_sims, _load_trading_strategy  # type: ignore
from api.sim_review import build_sim_strategy_review, write_sim_strategy_review  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("write", "preview"),
        nargs="?",
        default="write",
        help="Write the review artifact or print a preview only.",
    )
    args = parser.parse_args()

    sims = _load_sims()
    finance_brain = _load_finance_brain()
    trading_strategy = _load_trading_strategy()
    if args.command == "write":
        payload = write_sim_strategy_review(sims, finance_brain, trading_strategy)
        print(
            json.dumps(
                {
                    "status": payload.get("status"),
                    "generated_at": payload.get("generated_at"),
                    "next_review_at": payload.get("next_review_at"),
                    "summary": payload.get("summary"),
                },
                indent=2,
            )
        )
        return 0

    print(json.dumps(build_sim_strategy_review(sims, finance_brain, trading_strategy), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
