#!/usr/bin/env python3
"""
End-to-end trading cycle runner.

Stages:
  1. Fetch public market candles
  2. Classify ITC Telegram messages
  3. Run the paper-trading sims
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import itc_classify, market_stream, sim_runner


def run(
    *,
    config_path=None,
    features_path=None,
    full: bool = False,
    market_limit: int = 500,
    max_llm: int = 80,
    model=None,
    rules_only: bool = False,
    skip_market: bool = False,
    sim_id=None,
    symbols=None,
):
    if skip_market:
        print("==> market (skipped)")
    else:
        print("==> market")
        market_stream.run(
            config_path=market_stream.resolve_path(config_path, market_stream.CONFIG_ENV, market_stream.DEFAULT_CONFIG_PATH),
            symbols=symbols,
            limit=market_limit,
            full=full,
        )

    print("==> classify")
    itc_classify.run(
        full=full,
        rules_only=rules_only,
        max_llm=max_llm,
        model=model,
    )

    print("==> sim")
    sim_runner.run(
        sim_filter=sim_id,
        full=full,
        config_path=sim_runner.resolve_path(config_path, sim_runner.CONFIG_ENV, sim_runner.DEFAULT_CONFIG_PATH),
        features_path=sim_runner.resolve_path(features_path, sim_runner.FEATURES_ENV, sim_runner.DEFAULT_FEATURES_CONFIG_PATH),
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run market fetch + ITC classify + trading sims")
    parser.add_argument("--config", type=str, default=None, help="Override base trading config")
    parser.add_argument("--features-config", type=str, default=None, help="Override feature overlay config")
    parser.add_argument("--symbol", action="append", default=None, help="Override config symbols (repeatable)")
    parser.add_argument("--market-limit", type=int, default=500, help="Max candles per symbol/timeframe to fetch")
    parser.add_argument("--max-llm", type=int, default=80, help="Max LLM reclassification calls")
    parser.add_argument("--model", type=str, default=None, help="Override ITC classifier model")
    parser.add_argument("--sim", type=str, default=None, help="Run only one sim")
    parser.add_argument("--full", action="store_true", help="Reprocess all stages from scratch")
    parser.add_argument("--skip-market", action="store_true", help="Skip REST market fetch and use existing/live market files")
    parser.add_argument("--rules-only", action="store_true", help="Disable the LLM reclassification pass")
    args = parser.parse_args(argv)

    return run(
        config_path=args.config,
        features_path=args.features_config,
        full=args.full,
        market_limit=args.market_limit,
        max_llm=args.max_llm,
        model=args.model,
        rules_only=args.rules_only,
        skip_market=args.skip_market,
        sim_id=args.sim,
        symbols=args.symbol,
    )


if __name__ == "__main__":
    raise SystemExit(main())
