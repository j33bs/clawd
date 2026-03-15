#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.market_sentiment.producer import DEFAULT_CONFIG_PATH, DEFAULT_OUTPUT_PATH, run_market_sentiment  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Produce c_lawd market sentiment snapshot for Dali")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--print-json", action="store_true", help="Print the full snapshot JSON")
    args = parser.parse_args()

    try:
        snapshot = run_market_sentiment(
            config_path=Path(args.config).expanduser(),
            output_path=Path(args.output).expanduser(),
        )
    except Exception as exc:
        print(f"status=error error={exc}", file=sys.stderr)
        return 1
    if args.print_json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        agg = snapshot["aggregate"]
        model = snapshot["model"]
        print(
            f"status={snapshot['status']} "
            f"model={model['resolved'] or model['requested']} "
            f"sentiment={agg['sentiment']:+.3f} "
            f"confidence={agg['confidence']:.3f} "
            f"regime={agg['regime']} "
            f"sources={agg['sources_considered']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
