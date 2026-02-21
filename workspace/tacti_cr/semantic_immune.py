"""Semantic immune system for admission-time outlier quarantine."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_float, get_int, is_enabled
from .events import emit


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _vec(text: str, dim: int = 64) -> list[float]:
    tokens = [tok for tok in text.lower().split() if tok]
    out = [0.0] * dim
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % dim
        sign = 1.0 if (int(digest[8:10], 16) % 2 == 0) else -1.0
        out[idx] += sign
    return out


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _cos(a: list[float], b: list[float]) -> float:
    na = _norm(a)
    nb = _norm(b)
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def _paths(repo_root: Path) -> dict[str, Path]:
    base = repo_root / "workspace" / "state" / "semantic_immune"
    return {
        "stats": base / "stats.json",
        "quarantine": base / "quarantine.jsonl",
        "approvals": base / "approvals.jsonl",
    }


def _load_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"count": 0, "centroid": [0.0] * 64, "distances": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {"count": 0, "centroid": [0.0] * 64, "distances": []}


def _save_stats(path: Path, stats: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")


def _append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2:
        return s[n // 2]
    return 0.5 * (s[n // 2 - 1] + s[n // 2])


def _mad(values: list[float]) -> float:
    med = _median(values)
    return _median([abs(v - med) for v in values])


def _epitope_enabled() -> bool:
    return str(os.environ.get("OPENCLAW_SEMANTIC_IMMUNE_EPITOPES", "")).strip().lower() in {"1", "true", "yes", "on"} or str(
        os.environ.get("OPENCLAW_EPITOPE_CACHE", "")
    ).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_claim(claim: str) -> list[str]:
    text = str(claim or "").lower()
    return [tok for tok in re.findall(r"[a-z0-9_]+", text) if tok]


def _claim_signature(claim: str) -> dict[str, Any]:
    tokens = _normalize_claim(claim)
    digest = hashlib.sha256(" ".join(tokens).encode("utf-8")).hexdigest()[:16]
    return {"tokens": sorted(set(tokens)), "digest": digest}


def _jaccard(a_tokens: list[str], b_tokens: list[str]) -> float:
    aset = set(a_tokens or [])
    bset = set(b_tokens or [])
    if not aset and not bset:
        return 1.0
    if not aset or not bset:
        return 0.0
    inter = len(aset & bset)
    union = len(aset | bset)
    return float(inter) / float(union or 1)


class EpitopeCache:
    def __init__(self, capacity: int = 256):
        self.capacity = max(1, int(capacity))
        self._rows: list[dict[str, Any]] = []

    def add(self, claim: str, max_size: int | None = None) -> bool:
        signature = _claim_signature(claim)
        if not signature["tokens"]:
            return False
        cap = max(1, int(max_size if max_size is not None else self.capacity))
        self.capacity = cap
        self._rows.append(signature)
        if len(self._rows) > cap:
            self._rows = self._rows[-cap:]
        return True

    def match(self, claim: str, threshold: float = 0.6) -> bool:
        incoming = _claim_signature(claim)
        tokens = incoming.get("tokens", [])
        if not tokens:
            return False
        for row in self._rows:
            if _jaccard(tokens, row.get("tokens", [])) >= float(threshold):
                return True
        return False


_EPITOPE_CACHE = EpitopeCache(capacity=256)


def cache_epitope(losing_belief: str, *, max_len: int = 256, max_size: int | None = None) -> bool:
    if not _epitope_enabled():
        return False
    cap = int(max_size if max_size is not None else max_len)
    return _EPITOPE_CACHE.add(str(losing_belief or ""), max_size=cap)


def epitope_cache_hit(claim: str, *, threshold: float = 0.6) -> bool:
    if not _epitope_enabled():
        return False
    return _EPITOPE_CACHE.match(str(claim or ""), threshold=threshold)


def assess_content(repo_root: Path, content: str) -> dict[str, Any]:
    if not is_enabled("semantic_immune"):
        return {"ok": True, "reason": "semantic_immune_disabled", "quarantined": False}

    if epitope_cache_hit(content):
        digest = hashlib.sha256(str(content).encode("utf-8")).hexdigest()[:16]
        row = {
            "ts": _utc_now(),
            "content_hash": digest,
            "score": 1.0,
            "threshold": 0.6,
            "reason": "epitope_cache_hit",
        }
        paths = _paths(repo_root)
        _append(paths["quarantine"], {**row, "content": content})
        emit("tacti_cr.semantic_immune.quarantined", {k: row[k] for k in ("content_hash", "score", "threshold", "reason")})
        return {"ok": True, "quarantined": True, **row}

    paths = _paths(repo_root)
    stats = _load_stats(paths["stats"])
    centroid = [float(x) for x in stats.get("centroid", [0.0] * 64)]
    count = int(stats.get("count", 0))
    distances = [float(x) for x in stats.get("distances", [])][-400:]

    vector = _vec(content)
    score = 1.0 - _cos(vector, centroid)

    med = _median(distances) if distances else 0.2
    mad = _mad(distances) if distances else 0.05
    threshold = med + get_float("immune_mad_multiplier", 3.0, clamp=(1.0, 8.0)) * max(mad, 0.01)

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    quarantine = bool(count >= get_int("immune_min_count", 6, clamp=(1, 10000)) and score > threshold)
    row = {
        "ts": _utc_now(),
        "content_hash": digest,
        "score": round(score, 6),
        "threshold": round(threshold, 6),
        "reason": "out_of_distribution" if quarantine else "accepted",
    }

    if quarantine:
        _append(paths["quarantine"], {**row, "content": content})
        emit("tacti_cr.semantic_immune.quarantined", {k: row[k] for k in ("content_hash", "score", "threshold", "reason")})
        return {"ok": True, "quarantined": True, **row}

    # update healthy distribution
    new_count = count + 1
    if len(centroid) != len(vector):
        centroid = [0.0] * len(vector)
    centroid = [((centroid[i] * count) + vector[i]) / float(new_count) for i in range(len(vector))]
    distances.append(score)
    stats.update({"count": new_count, "centroid": centroid, "distances": distances[-400:]})
    _save_stats(paths["stats"], stats)
    emit(
        "tacti_cr.semantic_immune.accepted",
        {k: row[k] for k in ("content_hash", "score", "threshold", "reason")},
    )
    return {"ok": True, "quarantined": False, **row}


def approve_quarantine(repo_root: Path, content_hash: str) -> dict[str, Any]:
    paths = _paths(repo_root)
    target = str(content_hash)
    if not paths["quarantine"].exists():
        return {"ok": False, "reason": "quarantine_empty"}

    kept = []
    approved = None
    for line in paths["quarantine"].read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if str(row.get("content_hash")) == target and approved is None:
            approved = row
            continue
        kept.append(row)

    with paths["quarantine"].open("w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    if approved is None:
        return {"ok": False, "reason": "not_found", "content_hash": target}

    _append(paths["approvals"], {"ts": _utc_now(), "content_hash": target, "approved": True})
    emit("tacti_cr.semantic_immune.approved", {"content_hash": target})
    assess_content(repo_root, str(approved.get("content", "")))
    return {"ok": True, "content_hash": target}


__all__ = [
    "EpitopeCache",
    "_EPITOPE_CACHE",
    "assess_content",
    "approve_quarantine",
    "cache_epitope",
    "epitope_cache_hit",
]
