#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.models import KnowledgeUnit
from hivemind.redaction import redact_for_embedding
from hivemind.store import HiveMindStore


def cmd_query(args: argparse.Namespace) -> int:
    store = HiveMindStore()
    rows = store.search(agent_scope=args.agent, query=args.q, limit=args.limit)
    payload = []
    for row in rows:
        payload.append(
            {
                "kind": row.get("kind"),
                "source": row.get("source"),
                "agent_scope": row.get("agent_scope"),
                "score": row.get("score", 0),
                "created_at": row.get("created_at"),
                "content": redact_for_embedding(str(row.get("content", ""))),
                "metadata": row.get("metadata", {}),
            }
        )

    if args.json:
        print(json.dumps({"results": payload}, ensure_ascii=False, indent=2))
        return 0

    for item in payload:
        print(f"[{item['score']}] {item['kind']} {item['source']} ({item['agent_scope']})")
        print(item["content"])
        print("---")
    return 0


def cmd_store(args: argparse.Namespace) -> int:
    store = HiveMindStore()
    ku = KnowledgeUnit(
        kind=args.kind,
        source=args.source,
        agent_scope=args.agent_scope,
        ttl_days=args.ttl_days,
        metadata={},
    )
    result = store.put(ku, args.content)
    out = {
        "stored": bool(result.get("stored")),
        "reason": result.get("reason"),
        "content_hash": result.get("content_hash"),
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HiveMind memory query/store tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("query", help="query memory")
    q.add_argument("--agent", required=True)
    q.add_argument("--q", required=True)
    q.add_argument("--limit", type=int, default=5)
    q.add_argument("--json", action="store_true", help="emit JSON output")
    q.set_defaults(func=cmd_query)

    s = sub.add_parser("store", help="store a manual knowledge unit")
    s.add_argument("--kind", required=True)
    s.add_argument("--content", required=True)
    s.add_argument("--source", default="manual")
    s.add_argument("--agent-scope", default="main")
    s.add_argument("--ttl-days", type=int, default=None)
    s.add_argument("--json", action="store_true", help="emit JSON output")
    s.set_defaults(func=cmd_store)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
