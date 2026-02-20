from __future__ import annotations

import hashlib
import json
import os
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


def canonicalize(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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


def _episode_timestamp(episode: Dict[str, Any]) -> str:
    raw = episode.get("timestamp_utc") or episode.get("ts") or episode.get("timestamp")
    text = str(raw or "").strip()
    if not text:
        return ""
    if text.isdigit():
        try:
            ms = int(text)
            if ms > 10_000_000_000:
                return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            return datetime.fromtimestamp(ms, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            return ""
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _narrative_distill_enabled() -> bool:
    value = str(os.environ.get("OPENCLAW_NARRATIVE_DISTILL", "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


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
        timestamps = sorted(ts for ts in (_episode_timestamp(item) for item in cluster) if ts)
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
                "timestamp_utc": timestamps[0] if timestamps else "1970-01-01T00:00:00Z",
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
    if not _narrative_distill_enabled():
        return {"ok": True, "backend": "disabled", "path": "", "added": 0, "skipped_existing": 0}

    try:
        from hivemind.trails import TrailStore
    except Exception:
        import sys

        hivemind_pkg = Path(repo_root) / "workspace" / "hivemind" / "hivemind"
        if str(hivemind_pkg) not in sys.path:
            sys.path.insert(0, str(hivemind_pkg))
        from trails import TrailStore

    trails_path = repo_root / "workspace" / "hivemind" / "data" / "trails.jsonl"
    existing_semantic_keys: set[str] = set()
    if trails_path.exists():
        for line in trails_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            meta = row.get("meta", {})
            if not isinstance(meta, dict):
                continue
            if str(meta.get("namespace", "")) != "semantic":
                continue
            key = str(meta.get("semantic_key", "")).strip()
            if key:
                existing_semantic_keys.add(key)
    try:
        store = TrailStore(path=trails_path, half_life_hours=24.0 * 90.0)
        added = 0
        skipped = 0
        for item in entries:
            semantic_key = hashlib.sha256(
                canonicalize(
                    {
                        "fact": str(item.get("fact", "")),
                        "source_ids": list(item.get("source_ids", [])),
                    }
                )
            ).hexdigest()[:16]
            if semantic_key in existing_semantic_keys:
                skipped += 1
                continue
            store.add(
                {
                    "text": str(item.get("fact", "")),
                    "tags": ["semantic", *[str(t) for t in item.get("topics", [])[:3]]],
                    "strength": 1.0 + min(5.0, float(item.get("support_count", 1)) * 0.1),
                    "meta": {
                        "namespace": "semantic",
                        "semantic_key": semantic_key,
                        "support_count": int(item.get("support_count", 1)),
                        "source_ids": list(item.get("source_ids", [])),
                        "timestamp_utc": str(item.get("timestamp_utc", "")),
                    },
                }
            )
            existing_semantic_keys.add(semantic_key)
            added += 1
        return {"ok": True, "backend": "trails", "path": str(trails_path), "added": added, "skipped_existing": skipped}
    except Exception:
        fallback = repo_root / "workspace" / "memory" / "semantic_store.jsonl"
        existing_keys = set()
        if fallback.exists():
            for line in fallback.read_text(encoding="utf-8", errors="ignore").splitlines():
                raw = line.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    continue
                key = str((row if isinstance(row, dict) else {}).get("semantic_key", "")).strip()
                if key:
                    existing_keys.add(key)
        added = 0
        skipped = 0
        fallback.parent.mkdir(parents=True, exist_ok=True)
        with fallback.open("a", encoding="utf-8") as handle:
            for item in entries:
                semantic_key = hashlib.sha256(
                    canonicalize({"fact": str(item.get("fact", "")), "source_ids": list(item.get("source_ids", []))})
                ).hexdigest()[:16]
                if semantic_key in existing_keys:
                    skipped += 1
                    continue
                handle.write(json.dumps({**item, "semantic_key": semantic_key}, ensure_ascii=True) + "\n")
                existing_keys.add(semantic_key)
                added += 1
        return {"ok": True, "backend": "jsonl", "path": str(fallback), "added": added, "skipped_existing": skipped}


__all__ = ["distill_episodes", "read_episodic_events", "write_semantic_entries"]
