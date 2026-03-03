#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_topic(raw: str) -> str:
    topic = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    topic = re.sub(r"[^a-z0-9_]+", "", topic)
    topic = re.sub(r"_+", "_", topic).strip("_")
    return topic


def _parse_topics_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    topics: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = re.match(r"^\|\s*\*\*(?P<topic>[^*|]+)\*\*\s*\|", line.strip())
        if not match:
            continue
        topic = _normalize_topic(match.group("topic"))
        if topic and topic not in seen:
            seen.add(topic)
            topics.append(topic)
    return topics


def _topic_counts(papers_path: Path) -> tuple[int, dict[str, int]]:
    total = 0
    counts: dict[str, int] = {}
    if not papers_path.exists():
        return total, counts
    for line in papers_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        total += 1
        topic = _normalize_topic(row.get("topic", ""))
        if topic:
            counts[topic] = counts.get(topic, 0) + 1
    return total, counts


def analyze_gaps(*, papers_path: Path, topics_file: Path, low_coverage_threshold: int = 1, top_k: int = 5) -> dict[str, Any]:
    total_papers, counts = _topic_counts(papers_path)
    expected_topics = _parse_topics_file(topics_file)
    gaps = []
    threshold = max(0, int(low_coverage_threshold))
    for topic in expected_topics:
        count = int(counts.get(topic, 0))
        if count <= threshold:
            gaps.append(
                {
                    "topic": topic,
                    "count": count,
                    "status": "missing" if count == 0 else "low_coverage",
                }
            )
    gaps.sort(key=lambda item: (item["count"], item["topic"]))
    top_gaps = gaps[: max(1, int(top_k))]
    return {
        "ts_utc": _utc_now(),
        "type": "research_gap_report",
        "papers_total": total_papers,
        "topics_expected": len(expected_topics),
        "topics_observed": len(counts),
        "top_gaps": top_gaps,
        "sources": [str(papers_path), str(topics_file)],
    }


def publish_gap_report(*, report: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    kb_path = Path(repo_root) / "workspace" / "knowledge_base" / "data" / "research_gap_reports.jsonl"
    kb_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(report or {})
    signature_base = json.dumps(
        {
            "papers_total": payload.get("papers_total", 0),
            "topics_expected": payload.get("topics_expected", 0),
            "top_gaps": payload.get("top_gaps", []),
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    payload["signature"] = hashlib.sha256(signature_base.encode("utf-8")).hexdigest()
    payload["ts_utc"] = str(payload.get("ts_utc") or _utc_now())

    last_sig = None
    if kb_path.exists():
        for line in kb_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                last_sig = row.get("signature", last_sig)

    if last_sig == payload["signature"]:
        return {"ok": True, "path": str(kb_path), "appended": False, "reason": "unchanged_signature"}

    with kb_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return {"ok": True, "path": str(kb_path), "appended": True, "reason": "appended"}


__all__ = ["analyze_gaps", "publish_gap_report"]
