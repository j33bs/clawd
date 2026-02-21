from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from .intelligence.contradictions import detect_contradictions
from .intelligence.pruning import prune_expired_and_stale
from .intelligence.suggestions import generate_suggestions
from .intelligence.summaries import generate_cross_agent_summary
from .intelligence.utils import get_all_units_cached
from .store import HiveMindStore


def _can_view(agent: str, scope: str) -> bool:
    return scope == "shared" or scope == agent


def cmd_scan_contradictions(args: argparse.Namespace) -> int:
    store = HiveMindStore()
    units, _meta = get_all_units_cached(store, ttl_seconds=60)
    visible = [u for u in units if _can_view(args.agent, str(u.get("agent_scope", "shared")))]
    reports = detect_contradictions(visible)
    print(json.dumps({"contradictions": reports}, ensure_ascii=False, indent=2))
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    report = prune_expired_and_stale(dry_run=bool(args.dry_run))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    result = generate_cross_agent_summary(args.period)
    print(result.get("markdown", ""))
    return 0


def cmd_suggest(args: argparse.Namespace) -> int:
    suggestions = generate_suggestions(args.context, args.agent)
    print(json.dumps({"suggestions": suggestions}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HiveMind Phase 3 intelligence CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("scan-contradictions", help="scan visible memory for contradiction signals")
    c.add_argument("--agent", required=True)
    c.set_defaults(func=cmd_scan_contradictions)

    p = sub.add_parser("prune", help="prune expired/stale memory")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--agent", required=False, default="main")
    p.set_defaults(func=cmd_prune)

    d = sub.add_parser("digest", help="generate shared digest")
    d.add_argument("--period", default="7d")
    d.add_argument("--agent", required=False, default="main")
    d.set_defaults(func=cmd_digest)

    s = sub.add_parser("suggest", help="generate proactive suggestions")
    s.add_argument("--agent", required=True)
    s.add_argument("--context", default="")
    s.set_defaults(func=cmd_suggest)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
