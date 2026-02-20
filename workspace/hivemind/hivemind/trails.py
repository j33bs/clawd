from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4


DEFAULT_BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TRAILS_PATH = DEFAULT_BASE_DIR / "data" / "trails.jsonl"
DEFAULT_HALF_LIFE_HOURS = 24.0
EMBED_DIM = 24


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if text:
        try:
            dt = datetime.fromisoformat(text)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return _utc_now()


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: List[float]) -> float:
    return math.sqrt(_dot(a, a))


def _cosine(a: List[float], b: List[float]) -> float:
    na = _norm(a)
    nb = _norm(b)
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return _dot(a, b) / (na * nb)


def _embed_text(text: str, tags: List[str] | None = None, dim: int = EMBED_DIM) -> List[float]:
    vec = [0.0 for _ in range(dim)]
    chunks = [str(text or "").lower()]
    for tag in (tags or []):
        chunks.append(str(tag).lower())
    for chunk in chunks:
        for token in chunk.split():
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            bucket = int(digest[:8], 16) % dim
            sign = 1.0 if (int(digest[8:10], 16) % 2 == 0) else -1.0
            vec[bucket] += sign
    return vec


def _trail_valence_enabled() -> bool:
    value = str(
        os.environ.get(
            "OPENCLAW_TRAILS_VALENCE",
            os.environ.get("OPENCLAW_TRAIL_VALENCE", "0"),
        )
    ).strip().lower()
    return value in {"1", "true", "yes", "on"}


def dampen_valence_signature(signature: Any, hops: int = 1) -> Any:
    factor = 0.5 ** max(0, int(hops))
    if isinstance(signature, dict):
        return {str(k): round(float(v) * factor, 6) for k, v in signature.items() if isinstance(v, (int, float))}
    if isinstance(signature, list):
        return [round(float(v) * factor, 6) for v in signature if isinstance(v, (int, float))]
    if isinstance(signature, (int, float)):
        return round(float(signature) * factor, 6)
    return None


def _blend_valence_signature(previous: Any, current: Any, alpha: float = 0.5) -> Any:
    a = max(0.0, min(1.0, float(alpha)))
    if previous is None:
        return current
    if isinstance(previous, (int, float)) and isinstance(current, (int, float)):
        return round(((1.0 - a) * float(previous)) + (a * float(current)), 6)
    if isinstance(previous, list) and isinstance(current, list):
        width = min(len(previous), len(current))
        return [round(((1.0 - a) * float(previous[i])) + (a * float(current[i])), 6) for i in range(width)]
    if isinstance(previous, dict) and isinstance(current, dict):
        keys = sorted(set(previous.keys()) & set(current.keys()))
        return {
            str(k): round(((1.0 - a) * float(previous[k])) + (a * float(current[k])), 6)
            for k in keys
            if isinstance(previous.get(k), (int, float)) and isinstance(current.get(k), (int, float))
        }
    return current


class TrailStore:
    def __init__(self, path: Path | None = None, half_life_hours: float = DEFAULT_HALF_LIFE_HOURS):
        self.path = Path(path or DEFAULT_TRAILS_PATH)
        self.half_life_hours = max(0.5, float(half_life_hours))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def _write_all(self, rows: List[Dict[str, Any]]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def add(self, trail: Dict[str, Any]) -> str:
        return self.deposit(trail, valence=trail.get("valence_signature"))

    def deposit(self, trail: Dict[str, Any], valence: Any = None) -> str:
        text = str(trail.get("text", "")).strip()
        tags = [str(x) for x in (trail.get("tags") or []) if str(x)]
        embedding = trail.get("embedding")
        if not isinstance(embedding, list):
            embedding = _embed_text(text, tags=tags)
        embedding = [float(x) for x in embedding]
        now = _utc_now().isoformat()
        row = {
            "trail_id": str(trail.get("trail_id") or uuid4()),
            "text": text,
            "tags": tags,
            "embedding": embedding,
            "strength": float(trail.get("strength", 1.0) or 1.0),
            "meta": dict(trail.get("meta") or {}),
            "created_at": str(trail.get("created_at") or now),
            "updated_at": str(trail.get("updated_at") or now),
        }
        if _trail_valence_enabled() and (valence is not None or trail.get("valence_signature") is not None):
            valence_raw = valence if valence is not None else trail.get("valence_signature")
            hops = int(trail.get("valence_hops", 0) or 0)
            row["valence_signature"] = dampen_valence_signature(valence_raw, hops=hops)
            row["valence_hops"] = hops
            previous = None
            for prior in reversed(self._read_all()):
                if str(prior.get("text", "")).strip() == text and prior.get("valence_consensus") is not None:
                    previous = prior.get("valence_consensus")
                    break
                if str(prior.get("text", "")).strip() == text and prior.get("valence_signature") is not None:
                    previous = prior.get("valence_signature")
                    break
            row["valence_consensus"] = _blend_valence_signature(previous, row.get("valence_signature"), alpha=0.5)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row["trail_id"]

    def follow(self, text_or_embedding: str | List[float], now: Any = None):
        trails = self.query(text_or_embedding, k=1, now=now)
        if not trails:
            return None, None
        trail = dict(trails[0])
        if not _trail_valence_enabled():
            return trail, None
        source_signature = trail.get("valence_consensus", trail.get("valence_signature"))
        if source_signature is None:
            return trail, None
        inherited = dampen_valence_signature(source_signature, hops=1)
        return trail, inherited

    def _effective_strength(self, row: Dict[str, Any], now: datetime) -> float:
        updated = _parse_ts(row.get("updated_at") or row.get("created_at"))
        age_hours = max(0.0, (now - updated).total_seconds() / 3600.0)
        decay_factor = math.exp(-math.log(2.0) * (age_hours / self.half_life_hours))
        return float(row.get("strength", 0.0)) * decay_factor

    def query(self, text_or_embedding: str | List[float], k: int, now: Any = None) -> List[Dict[str, Any]]:
        current = _parse_ts(now) if now is not None else _utc_now()
        if isinstance(text_or_embedding, list):
            query_embedding = [float(x) for x in text_or_embedding]
        else:
            query_embedding = _embed_text(str(text_or_embedding), tags=None)

        scored: List[Dict[str, Any]] = []
        for row in self._read_all():
            embedding = row.get("embedding")
            if not isinstance(embedding, list):
                continue
            emb = [float(x) for x in embedding]
            similarity = max(0.0, _cosine(query_embedding, emb))
            effective = self._effective_strength(row, current) * similarity
            item = dict(row)
            item["similarity"] = similarity
            item["effective_strength"] = effective
            scored.append(item)
        scored.sort(key=lambda item: (-float(item["effective_strength"]), str(item.get("trail_id", ""))))
        return scored[: max(1, int(k))]

    def decay(self, now: Any = None) -> Dict[str, Any]:
        current = _parse_ts(now) if now is not None else _utc_now()
        rows = self._read_all()
        changed = 0
        for row in rows:
            prev = float(row.get("strength", 0.0))
            updated = _parse_ts(row.get("updated_at") or row.get("created_at"))
            age_hours = max(0.0, (current - updated).total_seconds() / 3600.0)
            if age_hours <= 0:
                continue
            factor = math.exp(-math.log(2.0) * (age_hours / self.half_life_hours))
            row["strength"] = max(0.001, prev * factor)
            row["updated_at"] = current.isoformat()
            changed += 1
        if changed:
            self._write_all(rows)
        return {"ok": True, "changed": changed, "path": str(self.path)}

    def reinforce(self, trail_id: str, delta: float) -> bool:
        target = str(trail_id)
        rows = self._read_all()
        changed = False
        now = _utc_now().isoformat()
        for row in rows:
            if str(row.get("trail_id")) != target:
                continue
            row["strength"] = max(0.001, float(row.get("strength", 0.0)) + float(delta))
            row["updated_at"] = now
            changed = True
            break
        if changed:
            self._write_all(rows)
        return changed

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "path": str(self.path),
            "half_life_hours": self.half_life_hours,
            "count": len(self._read_all()),
        }

    @classmethod
    def load(cls, payload: Dict[str, Any]) -> "TrailStore":
        return cls(
            path=Path(str(payload.get("path") or DEFAULT_TRAILS_PATH)),
            half_life_hours=float(payload.get("half_life_hours", DEFAULT_HALF_LIFE_HOURS)),
        )
