"""Dream consolidation engine with deterministic fallback semantics."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .config import get_float, is_enabled


@dataclass
class DreamItem:
    item_id: str
    content: str
    reinforced_at: str
    strength: float


def _utc_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_\-]+", (text or "").lower()))


def _jaccard(a: str, b: str) -> float:
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))


def _state_paths(repo_root: Path) -> dict[str, Path]:
    return {
        "store": repo_root / "workspace" / "hivemind" / "data" / "dream_store.jsonl",
        "report_dir": repo_root / "workspace" / "memory" / "dream_reports",
        "long_term": repo_root / "workspace" / "memory" / "LONG_TERM.md",
    }


def _memory_sources(repo_root: Path, day: str) -> list[Path]:
    candidates = [
        repo_root / "workspace" / "memory" / f"{day}.md",
        repo_root / "nodes" / "dali" / "memory" / f"{day}.md",
    ]
    return [p for p in candidates if p.exists()]


def _extract_candidates(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        out.append(line)
    return out


def _load_store(path: Path) -> list[DreamItem]:
    if not path.exists():
        return []
    rows: list[DreamItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        rows.append(
            DreamItem(
                item_id=str(payload.get("item_id") or ""),
                content=str(payload.get("content") or ""),
                reinforced_at=str(payload.get("reinforced_at") or ""),
                strength=float(payload.get("strength", 1.0)),
            )
        )
    return rows


def _save_store(path: Path, rows: list[DreamItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                json.dumps(
                    {
                        "item_id": row.item_id,
                        "content": row.content,
                        "reinforced_at": row.reinforced_at,
                        "strength": round(float(row.strength), 6),
                    },
                    ensure_ascii=True,
                )
                + "\n"
            )


def _apply_decay(rows: list[DreamItem], now: datetime, half_life_days: float) -> list[DreamItem]:
    out: list[DreamItem] = []
    for row in rows:
        try:
            ts = datetime.fromisoformat(row.reinforced_at.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            ts = now
        age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
        if age_days >= 7.0:
            factor = math.exp(-math.log(2.0) * (age_days / max(0.25, half_life_days)))
            row = DreamItem(row.item_id, row.content, row.reinforced_at, row.strength * factor)
        out.append(row)
    return out


def _cluster_insights(candidates: list[str], top_n: int = 5) -> list[str]:
    # Deterministic: rank by token cardinality then lexical content.
    scored = []
    for line in candidates:
        tokens = _tokenize(line)
        if len(tokens) < 3:
            continue
        scored.append((len(tokens), line))
    scored.sort(key=lambda x: (-x[0], x[1]))
    insights = [line for _, line in scored[:top_n]]
    while len(insights) < top_n:
        insights.append(f"No additional emergent pattern #{len(insights)+1}")
    return insights


def prune_competing_clusters(clusters, sim_threshold, max_merge_per_pass=1):
    """
    Deterministically merge highly similar clusters, decaying weaker competitors.
    Enabled only when OPENCLAW_DREAM_PRUNE is truthy.
    """
    if not is_enabled("dream_consolidation"):
        return list(clusters or [])
    if str(os.environ.get("OPENCLAW_DREAM_PRUNE", "0")).strip().lower() not in {"1", "true", "yes", "on"}:
        return list(clusters or [])

    rows = [dict(item) for item in (clusters or []) if isinstance(item, dict)]
    if len(rows) <= 1:
        return rows

    merges_left = max(1, int(max_merge_per_pass))
    while merges_left > 0:
        candidate = None
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a = rows[i]
                b = rows[j]
                text_a = str(a.get("text", ""))
                text_b = str(b.get("text", ""))
                sim = _jaccard(text_a, text_b)
                if sim < float(sim_threshold):
                    continue
                key = (
                    -sim,
                    str(a.get("cluster_id", a.get("id", i))),
                    str(b.get("cluster_id", b.get("id", j))),
                )
                if candidate is None or key < candidate[0]:
                    candidate = (key, i, j, sim)
        if candidate is None:
            break

        _, i, j, _sim = candidate
        left = rows[i]
        right = rows[j]
        lw = float(left.get("weight", 1.0) or 1.0)
        rw = float(right.get("weight", 1.0) or 1.0)
        if rw > lw or (rw == lw and str(right.get("cluster_id", right.get("id", ""))) < str(left.get("cluster_id", left.get("id", "")))):
            left, right = right, left
            lw, rw = rw, lw

        left["weight"] = round(lw + (rw * 0.25), 6)
        left["absorbed"] = sorted(set([*left.get("absorbed", []), str(right.get("cluster_id", right.get("id", "")))]))
        right["weight"] = round(rw * 0.5, 6)
        rows = [row for idx, row in enumerate(rows) if idx not in {i, j}]
        rows.append(left)
        merges_left -= 1

    rows.sort(key=lambda row: (-float(row.get("weight", 1.0) or 1.0), str(row.get("cluster_id", row.get("id", "")))))
    return rows


def run_consolidation(repo_root: Path, *, day: str, now: datetime | None = None) -> dict[str, Any]:
    if not is_enabled("dream_consolidation"):
        return {"ok": False, "reason": "dream_consolidation_disabled"}

    now_dt = _utc_now(now)
    paths = _state_paths(repo_root)
    sources = _memory_sources(repo_root, day)
    source_lines: list[str] = []
    for src in sources:
        source_lines.extend(_extract_candidates(src.read_text(encoding="utf-8", errors="ignore")))

    store = _load_store(paths["store"])
    dedup_threshold = get_float("dream_dedup_threshold", 0.72, clamp=(0.1, 1.0))

    added = 0
    for line in source_lines:
        if not line:
            continue
        best = None
        best_sim = 0.0
        for item in store:
            sim = _jaccard(item.content, line)
            if sim > best_sim:
                best_sim = sim
                best = item
        if best is not None and best_sim >= dedup_threshold:
            best.reinforced_at = now_dt.isoformat().replace("+00:00", "Z")
            best.strength = min(2.0, best.strength + 0.15)
            continue
        digest = hashlib.sha256(line.encode("utf-8")).hexdigest()[:16]
        store.append(
            DreamItem(
                item_id=digest,
                content=line,
                reinforced_at=now_dt.isoformat().replace("+00:00", "Z"),
                strength=1.0,
            )
        )
        added += 1

    half_life_days = get_float("dream_decay_half_life_days", 14.0, clamp=(1.0, 120.0))
    decayed = _apply_decay(store, now_dt, half_life_days)
    _save_store(paths["store"], decayed)

    insights = _cluster_insights([x.content for x in decayed], top_n=5)

    report_path = paths["report_dir"] / f"{day}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = [
        f"# Dream Report {day}",
        "",
        f"- generated_at: {now_dt.isoformat().replace('+00:00', 'Z')}",
        f"- source_items: {len(source_lines)}",
        f"- store_items: {len(decayed)}",
        f"- newly_added: {added}",
        "",
        "## Emergent Insights",
    ]
    for insight in insights:
        report.append(f"- {insight}")
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    long_term = paths["long_term"]
    long_term.parent.mkdir(parents=True, exist_ok=True)
    if not long_term.exists():
        long_term.write_text("# Long-term Memory\n\n", encoding="utf-8")
    with long_term.open("a", encoding="utf-8") as f:
        f.write(f"\n## Dream Consolidation {day}\n")
        for insight in insights:
            f.write(f"- {insight}\n")

    return {
        "ok": True,
        "day": day,
        "source_count": len(source_lines),
        "store_count": len(decayed),
        "newly_added": added,
        "report_path": str(report_path),
        "store_path": str(paths["store"]),
        "long_term_path": str(long_term),
        "insights": insights,
    }


__all__ = ["run_consolidation", "prune_competing_clusters"]
