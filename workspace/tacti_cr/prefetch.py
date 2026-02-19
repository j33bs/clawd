"""Predictive context prefetcher with deterministic topic prediction and adaptive depth."""

from __future__ import annotations

import json
import re
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_int, is_enabled


class PrefetchCache:
    def __init__(self, repo_root: Path | None = None):
        root = Path(repo_root or Path(__file__).resolve().parents[2])
        self.cache_path = root / "workspace" / "state" / "prefetch" / "cache.jsonl"
        self.index_path = root / "workspace" / "state" / "prefetch" / "index.json"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"hits": 0, "misses": 0, "depth": 3, "lru": []}
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload.setdefault("hits", 0)
                payload.setdefault("misses", 0)
                payload.setdefault("depth", 3)
                payload.setdefault("lru", [])
                return payload
        except Exception:
            pass
        return {"hits": 0, "misses": 0, "depth": 3, "lru": []}

    def _save_index(self, idx: dict[str, Any]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(idx, indent=2) + "\n", encoding="utf-8")

    def _append(self, row: dict[str, Any]) -> None:
        with self.cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    def record_prefetch(self, topic: str, docs: list[str]) -> None:
        idx = self._load_index()
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        key = f"{topic}:{ts}"
        idx["lru"].append(key)
        idx["lru"] = idx["lru"][-200:]
        self._append({"ts": ts, "topic": topic, "docs": docs})
        self._save_index(idx)

    def record_hit(self, hit: bool) -> dict[str, Any]:
        idx = self._load_index()
        if hit:
            idx["hits"] = int(idx.get("hits", 0)) + 1
        else:
            idx["misses"] = int(idx.get("misses", 0)) + 1
        total = int(idx["hits"]) + int(idx["misses"])
        hit_rate = (float(idx["hits"]) / total) if total > 0 else 1.0
        if total >= 100 and hit_rate < 0.4:
            idx["depth"] = max(1, int(idx.get("depth", 3)) - 1)
        self._save_index(idx)
        return {"hit_rate": hit_rate, "depth": idx["depth"], "total": total}

    def depth(self) -> int:
        return int(self._load_index().get("depth", 3))


def predict_topics(token_stream: str, *, last_n: int = 40, top_k: int = 3) -> list[str]:
    toks = re.findall(r"[A-Za-z0-9_\-]+", token_stream.lower())
    window = toks[-max(1, int(last_n)) :]
    counts = Counter(window)
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return [tok for tok, _ in ranked[: max(1, int(top_k))]]


def prefetch_context(token_stream: str, query_fn, *, repo_root: Path | None = None) -> dict[str, Any]:
    if not is_enabled("prefetch"):
        return {"ok": False, "reason": "prefetch_disabled", "topics": []}
    cache = PrefetchCache(repo_root=repo_root)
    topics = predict_topics(token_stream, top_k=cache.depth())
    docs = []
    for topic in topics:
        docs.extend(query_fn(topic))
    cache.record_prefetch("|".join(topics), docs)
    return {"ok": True, "topics": topics, "docs": docs}


__all__ = ["PrefetchCache", "predict_topics", "prefetch_context"]
