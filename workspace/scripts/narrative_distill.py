from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _norm_tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[A-Za-z0-9_./@-]+", str(text or "").lower()) if t]


def _jaccard_tokens(a: str, b: str) -> float:
    ta = set(_norm_tokens(a))
    tb = set(_norm_tokens(b))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return float(len(ta & tb)) / float(len(ta | tb))


def _extract_entities(text: str) -> List[str]:
    raw = re.findall(r"(?:@[A-Za-z0-9_]+|[A-Z][A-Za-z0-9_./-]+|[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8})", str(text or ""))
    out = sorted({token.strip() for token in raw if token.strip()})
    return out[:10]


def _extract_topics(texts: Iterable[str], top_n: int = 5) -> List[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        for tok in _norm_tokens(text):
            if tok in STOPWORDS or tok.isdigit() or len(tok) <= 2:
                continue
            counts[tok] += 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [token for token, _ in ordered[: max(1, int(top_n))]]


def _episode_text(episode: Dict[str, Any]) -> str:
    for key in ("text", "content", "message", "summary"):
        value = episode.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _episode_id(episode: Dict[str, Any], fallback_text: str) -> str:
    for key in ("id", "event_id", "episode_id"):
        value = episode.get(key)
        if value:
            return str(value)
    digest = hashlib.sha256(fallback_text.encode("utf-8")).hexdigest()
    return digest[:16]


def distill_episodes(episodes, max_items=50):
    rows: List[Dict[str, Any]] = []
    for item in episodes or []:
        if isinstance(item, dict):
            rows.append(item)

    clusters: List[List[Dict[str, Any]]] = []
    for row in rows:
        text = _episode_text(row)
        if not text:
            continue
        placed = False
        for cluster in clusters:
            anchor = _episode_text(cluster[0])
            if _jaccard_tokens(text, anchor) >= 0.72:
                cluster.append(row)
                placed = True
                break
        if not placed:
            clusters.append([row])

    distilled: List[Dict[str, Any]] = []
    for cluster in clusters:
        texts = [_episode_text(item) for item in cluster if _episode_text(item)]
        if not texts:
            continue
        ids = sorted({_episode_id(item, texts[idx]) for idx, item in enumerate(cluster)})
        entities = sorted({entity for text in texts for entity in _extract_entities(text)})
        topics = _extract_topics(texts)
        anchor = sorted(texts, key=lambda value: (-len(_norm_tokens(value)), value))[0]
        distilled.append(
            {
                "fact": anchor,
                "entities": entities[:12],
                "topics": topics,
                "support_count": len(texts),
                "source_ids": ids,
                "timestamp_utc": _utc_now(),
            }
        )

    distilled.sort(
        key=lambda item: (
            -int(item.get("support_count", 0)),
            str(item.get("fact", "")),
            "|".join(item.get("source_ids", [])),
        )
    )
    return distilled[: max(1, int(max_items))]


def read_episodic_events(path: Path, last_n: int = 200) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            payload.setdefault("id", str(payload.get("ts", "")))
            payload.setdefault("text", str(payload.get("event", "")))
            items.append(payload)
    return items[-max(1, int(last_n)) :]


def write_semantic_entries(entries: List[Dict[str, Any]], repo_root: Path) -> Dict[str, Any]:
    try:
        from hivemind.trails import TrailStore
    except Exception:
        import sys

        hivemind_pkg = Path(repo_root) / "workspace" / "hivemind" / "hivemind"
        if str(hivemind_pkg) not in sys.path:
            sys.path.insert(0, str(hivemind_pkg))
        from trails import TrailStore

    trails_path = repo_root / "workspace" / "hivemind" / "data" / "trails.jsonl"
    try:
        store = TrailStore(path=trails_path, half_life_hours=24.0 * 90.0)
        added = 0
        for item in entries:
            store.add(
                {
                    "text": str(item.get("fact", "")),
                    "tags": ["semantic", *[str(t) for t in item.get("topics", [])[:3]]],
                    "strength": 1.0 + min(5.0, float(item.get("support_count", 1)) * 0.1),
                    "meta": {
                        "namespace": "semantic",
                        "support_count": int(item.get("support_count", 1)),
                        "source_ids": list(item.get("source_ids", [])),
                        "timestamp_utc": str(item.get("timestamp_utc", "")),
                    },
                }
            )
            added += 1
        return {"ok": True, "backend": "trails", "path": str(trails_path), "added": added}
    except Exception:
        fallback = repo_root / "workspace" / "memory" / "semantic_store.jsonl"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        with fallback.open("a", encoding="utf-8") as handle:
            for item in entries:
                handle.write(json.dumps(item, ensure_ascii=True) + "\n")
        return {"ok": True, "backend": "jsonl", "path": str(fallback), "added": len(entries)}


__all__ = ["distill_episodes", "read_episodic_events", "write_semantic_entries"]
