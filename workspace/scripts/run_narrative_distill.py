#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from narrative_distill import distill_episodes, read_episodic_events, write_semantic_entries


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description="Distill episodic events into semantic memory entries.")
    parser.add_argument("--source", default="workspace/state/tacti_cr/events.jsonl", help="episodic JSONL source")
    parser.add_argument("--fallback-source", default="itc/llm_router_events.jsonl", help="fallback episodic source")
    parser.add_argument("--last-n", type=int, default=200, help="number of events to read")
    parser.add_argument("--max-items", type=int, default=50, help="maximum semantic entries to emit")
    args = parser.parse_args()

    root = _repo_root()
    source = root / args.source
    fallback = root / args.fallback_source

    episodes = read_episodic_events(source, last_n=args.last_n)
    source_used = source
    if not episodes and fallback.exists():
        episodes = read_episodic_events(fallback, last_n=args.last_n)
        source_used = fallback

    entries = distill_episodes(episodes, max_items=args.max_items)
    write_result = write_semantic_entries(entries, repo_root=root)

    audit_dir = root / "workspace" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"narrative_distill_{_utc_stamp()}.md"
    audit_path.write_text(
        "\n".join(
            [
                "# Narrative Distill Run",
                "",
                f"- source: {source_used}",
                f"- episodes_read: {len(episodes)}",
                f"- entries_written: {len(entries)}",
                f"- backend: {write_result.get('backend')}",
                f"- target_path: {write_result.get('path')}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "ok": True,
        "source": str(source_used),
        "episodes_read": len(episodes),
        "entries_written": len(entries),
        "backend": write_result.get("backend"),
        "target_path": write_result.get("path"),
        "audit_path": str(audit_path),
    }
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
