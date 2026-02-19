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
from hivemind.dynamics_pipeline import TactiDynamicsPipeline
from hivemind.integrations.main_flow_hook import (
    dynamics_flags_enabled,
    resolve_agent_ids,
    stable_seed,
)
from hivemind.intelligence.contradictions import detect_contradictions
from hivemind.intelligence.pruning import prune_expired_and_stale
from hivemind.intelligence.suggestions import generate_suggestions
from hivemind.intelligence.summaries import generate_cross_agent_summary

DYNAMICS_STATE_PATH = REPO_ROOT / "workspace" / "hivemind" / "data" / "tacti_dynamics_snapshot.json"


def _any_dynamics_enabled() -> bool:
    return dynamics_flags_enabled()


def _load_dynamics_pipeline(agent: str, rows: list[dict]) -> TactiDynamicsPipeline:
    candidates = {str(agent)}
    for row in rows:
        scope = str(row.get("agent_scope", "")).strip()
        if scope and scope != "shared":
            candidates.add(scope)
    resolved = resolve_agent_ids(
        context={"intent": "memory_query", "source_agent": str(agent)},
        candidates=sorted(candidates),
    )
    if str(agent) not in resolved:
        resolved.append(str(agent))
    resolved = sorted(dict.fromkeys(str(x) for x in resolved if str(x).strip()))
    seed = stable_seed(resolved, session_id=f"memory:{agent}")

    if DYNAMICS_STATE_PATH.exists():
        try:
            payload = json.loads(DYNAMICS_STATE_PATH.read_text(encoding="utf-8"))
            pipeline = TactiDynamicsPipeline.load(payload)
            if sorted(dict.fromkeys(str(x) for x in pipeline.agent_ids)) == resolved:
                return pipeline
        except Exception:
            pass
    return TactiDynamicsPipeline(agent_ids=resolved, seed=seed)


def _save_dynamics_pipeline(pipeline: TactiDynamicsPipeline) -> None:
    DYNAMICS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DYNAMICS_STATE_PATH.write_text(json.dumps(pipeline.snapshot(), indent=2) + "\n", encoding="utf-8")


def cmd_query(args: argparse.Namespace) -> int:
    store = HiveMindStore()
    rows = store.search(agent_scope=args.agent, query=args.q, limit=args.limit)
    store.log_event("query", agent=args.agent, query=args.q, limit=args.limit)

    dynamics_report = None
    if _any_dynamics_enabled():
        pipeline = _load_dynamics_pipeline(args.agent, rows)
        plan = pipeline.plan_consult_order(
            source_agent=args.agent,
            target_intent="memory_query",
            context_text=args.q,
            candidate_agents=[str(x) for x in pipeline.agent_ids if str(x) != str(args.agent)],
            n_paths=3,
        )
        consult_order = plan.get("consult_order", [])
        rank = {agent: idx for idx, agent in enumerate(consult_order)}
        rows.sort(key=lambda row: (rank.get(str(row.get("agent_scope", "")), 999), -int(row.get("score", 0))))
        reward = float(rows[0].get("score", 0)) / 5.0 if rows else -0.2
        top_path = plan.get("paths", [[args.agent]])[0]
        pipeline.observe_outcome(
            source_agent=args.agent,
            path=[str(x) for x in top_path],
            success=bool(rows),
            latency=0.0,
            tokens=float(len(args.q.split())),
            reward=reward,
            context_text=args.q,
        )
        _save_dynamics_pipeline(pipeline)
        store.log_event("dynamics_query_plan", agent=args.agent, order=consult_order, reward=reward)
        dynamics_report = {
            "consult_order": consult_order,
            "paths": plan.get("paths", []),
            "scores": plan.get("scores", {}),
            "trail_bias": plan.get("trail_bias", {}),
            "reservoir": plan.get("reservoir", {}),
        }

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
        out = {"results": payload}
        if dynamics_report is not None:
            out["dynamics"] = dynamics_report
        print(json.dumps(out, ensure_ascii=False, indent=2))
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


def cmd_scan_contradictions(args: argparse.Namespace) -> int:
    store = HiveMindStore()
    reports = detect_contradictions(store.all_units())
    if args.output == "json":
        print(json.dumps({"contradictions": reports}, ensure_ascii=False, indent=2))
    else:
        for item in reports:
            print(f"{item['severity']} {item['id']}: {item['reason']}")
    return 0


def cmd_suggest(args: argparse.Namespace) -> int:
    suggestions = generate_suggestions(args.context, args.agent)
    if args.output == "json":
        print(json.dumps({"suggestions": suggestions}, ensure_ascii=False, indent=2))
    else:
        for item in suggestions:
            print(f"[{item['type']}] {item['message']}")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    report = prune_expired_and_stale(dry_run=bool(args.dry_run))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    result = generate_cross_agent_summary(args.period)
    if args.output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("markdown", ""))
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

    c = sub.add_parser("scan-contradictions", help="scan memory for contradiction signals")
    c.add_argument("--output", choices=["json", "text"], default="text")
    c.set_defaults(func=cmd_scan_contradictions)

    g = sub.add_parser("suggest", help="generate proactive suggestions")
    g.add_argument("--agent", required=True)
    g.add_argument("--context", required=True)
    g.add_argument("--output", choices=["json", "text"], default="text")
    g.set_defaults(func=cmd_suggest)

    p = sub.add_parser("prune", help="prune expired/stale memory")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_prune)

    d = sub.add_parser("digest", help="generate cross-agent digest")
    d.add_argument("--period", default="7d")
    d.add_argument("--output", choices=["markdown", "json"], default="markdown")
    d.set_defaults(func=cmd_digest)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
