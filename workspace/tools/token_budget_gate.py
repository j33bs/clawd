#!/usr/bin/env python3
"""
token_budget_gate.py — Daily token budget circuit breaker for automated jobs.

Reads today's token_usage.jsonl log, sums total_tokens, and compares against
MAX_DAILY_TOKENS. Jobs that would exceed the budget are SKIP or deferred.

Usage:
  # Check if a job is within budget before running it:
  python3 workspace/tools/token_budget_gate.py --job daily_briefing --estimate 8000
  # Exit 0 = proceed, Exit 1 = skip

  # Print today's token usage summary:
  python3 workspace/tools/token_budget_gate.py --summary

  # Python API:
  from token_budget_gate import check_budget
  if check_budget("research_ingest", estimated_cost=15000):
      run_research_ingest()

Environment:
  MAX_DAILY_TOKENS=50000     — Hard ceiling per UTC day (default: 50,000)
  OPENCLAW_TOKEN_LOG_PATH    — Override path to token_usage.jsonl
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = WORKSPACE / "logs" / "token_usage.jsonl"
LOG_PATH = Path(os.getenv("OPENCLAW_TOKEN_LOG_PATH", str(DEFAULT_LOG_PATH)))
MAX_DAILY_TOKENS = int(os.getenv("MAX_DAILY_TOKENS", "50000"))


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def get_tokens_used_today(log_path: Path = LOG_PATH) -> int:
    """Sum total_tokens from today's (UTC) log entries."""
    today = datetime.now(timezone.utc).date().isoformat()  # e.g. "2026-03-04"
    total = 0
    if not log_path.exists():
        return 0
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = str(entry.get("ts_utc") or entry.get("timestamp") or "")
                if ts.startswith(today):
                    total += int(entry.get("total_tokens") or 0)
    except OSError:
        pass
    return total


def check_budget(
    job_name: str,
    estimated_cost: int,
    on_fail: str = "skip",
    log_path: Path = LOG_PATH,
    max_daily: int = MAX_DAILY_TOKENS,
    verbose: bool = True,
) -> bool:
    """
    Check if a job fits within the remaining daily token budget.

    Args:
        job_name:       Human-readable job name for logging.
        estimated_cost: Estimated token cost of the job.
        on_fail:        Action hint on budget exhaustion ("skip", "defer_24h", "use_cached").
        log_path:       Path to token_usage.jsonl.
        max_daily:      Daily token ceiling.
        verbose:        Print status to stdout.

    Returns:
        True  — job is within budget, proceed.
        False — budget exhausted, apply on_fail action.
    """
    used = get_tokens_used_today(log_path)
    remaining = max_daily - used

    if estimated_cost > remaining:
        if verbose:
            print(
                f"[token_budget_gate] {job_name}: SKIP — "
                f"used={used} remaining={remaining} estimate={estimated_cost} "
                f"max={max_daily} on_fail={on_fail}",
                file=sys.stderr,
            )
        return False

    if verbose:
        print(
            f"[token_budget_gate] {job_name}: PROCEED — "
            f"used={used} remaining={remaining} estimate={estimated_cost} max={max_daily}"
        )
    return True


def usage_summary(log_path: Path = LOG_PATH, max_daily: int = MAX_DAILY_TOKENS) -> dict:
    """Return a summary dict of today's token usage vs budget."""
    used = get_tokens_used_today(log_path)
    return {
        "date_utc":     datetime.now(timezone.utc).date().isoformat(),
        "used":         used,
        "max_daily":    max_daily,
        "remaining":    max_daily - used,
        "pct_used":     round(100 * used / max_daily, 1) if max_daily > 0 else 0,
        "log_path":     str(log_path),
        "log_exists":   log_path.exists(),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Daily token budget gate")
    parser.add_argument("--job", default="", help="Job name")
    parser.add_argument("--estimate", type=int, default=0, help="Estimated token cost")
    parser.add_argument("--on-fail", default="skip", help="Action on budget exhaustion")
    parser.add_argument("--summary", action="store_true", help="Print today's usage summary")
    parser.add_argument("--max", type=int, default=MAX_DAILY_TOKENS, help="Override max daily tokens")
    args = parser.parse_args()

    if args.summary:
        print(json.dumps(usage_summary(max_daily=args.max), indent=2))
        sys.exit(0)

    if not args.job or args.estimate <= 0:
        parser.print_help()
        sys.exit(2)

    ok = check_budget(args.job, args.estimate, on_fail=args.on_fail, max_daily=args.max)
    sys.exit(0 if ok else 1)
