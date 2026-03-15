from __future__ import annotations

import hashlib
import math
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import append_jsonl, utc_now_iso
from .logging_utils import JsonlLogger
from .paths import NOVELTY_ARCHIVE_DIR, RUNTIME_LOGS, ensure_runtime_dirs

EMBED_DIM = 48


@dataclass
class ArchiveDecision:
    archived: bool
    duplicate: bool
    similarity: float
    entry_id: str


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return math.sqrt(_dot(a, a))


def _cosine(a: list[float], b: list[float]) -> float:
    na = _norm(a)
    nb = _norm(b)
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return _dot(a, b) / (na * nb)


def _embed_text(text: str, dim: int = EMBED_DIM) -> list[float]:
    vec = [0.0] * dim
    for token in str(text or "").lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % dim
        sign = 1.0 if (int(digest[8:10], 16) % 2 == 0) else -1.0
        vec[idx] += sign
    return vec


class NoveltyArchive:
    def __init__(
        self,
        *,
        archive_dir: Path = NOVELTY_ARCHIVE_DIR,
        similarity_threshold: float = 0.93,
    ):
        ensure_runtime_dirs()
        self.archive_dir = archive_dir
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.entries_path = self.archive_dir / "entries.jsonl"
        self.similarity_threshold = max(0.0, min(0.999, float(similarity_threshold)))
        self.log = JsonlLogger(RUNTIME_LOGS / "novelty_archive.log")

    def _iter_entries(self, limit: int = 600) -> list[dict[str, Any]]:
        if not self.entries_path.exists():
            return []
        lines = self.entries_path.read_text(encoding="utf-8", errors="replace").splitlines()
        out: list[dict[str, Any]] = []
        for raw in lines[-limit:]:
            text = raw.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if isinstance(payload, dict):
                out.append(payload)
        return out

    def _nearest_similarity(self, embedding: list[float]) -> float:
        nearest = 0.0
        for row in self._iter_entries(limit=1200):
            emb = row.get("embedding")
            if not isinstance(emb, list):
                continue
            try:
                other = [float(x) for x in emb]
            except Exception:
                continue
            nearest = max(nearest, _cosine(embedding, other))
        return nearest

    def archive(
        self,
        *,
        curiosity_seed: str,
        exploration_path: list[str],
        result_text: str,
        result_novelty_score: float,
        telemetry_snapshot: dict[str, Any],
        source_query: str,
        source: str = "runtime",
    ) -> ArchiveDecision:
        entry_id = hashlib.sha256(
            f"{curiosity_seed}|{utc_now_iso()}|{source_query}".encode("utf-8")
        ).hexdigest()[:16]
        joined_path = " | ".join(str(step) for step in exploration_path)
        embedding = _embed_text(f"{source_query} {joined_path} {result_text}")
        similarity = self._nearest_similarity(embedding)
        duplicate = similarity >= self.similarity_threshold

        row = {
            "entry_id": entry_id,
            "ts": utc_now_iso(),
            "curiosity_seed": str(curiosity_seed),
            "source_query": str(source_query),
            "source": str(source),
            "exploration_path": [str(step) for step in exploration_path],
            "result_text": str(result_text),
            "result_novelty_score": float(result_novelty_score),
            "telemetry_snapshot": dict(telemetry_snapshot or {}),
            "embedding": embedding,
            "duplicate": bool(duplicate),
            "similarity": round(float(similarity), 6),
        }
        append_jsonl(self.entries_path, row)
        self.log.log(
            "archive_write",
            entry_id=entry_id,
            duplicate=duplicate,
            similarity=round(similarity, 6),
            novelty_score=float(result_novelty_score),
        )
        return ArchiveDecision(
            archived=not duplicate,
            duplicate=duplicate,
            similarity=similarity,
            entry_id=entry_id,
        )


__all__ = ["NoveltyArchive", "ArchiveDecision"]
