from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REVIEW_QUEUE = REPO_ROOT / "workspace" / "hivemind" / "review_queue.json"
_NEGATIONS = {"not", "never", "no", "avoid", "don't", "do_not", "cannot", "can't", "instead"}


def _ku_id(ku: Dict[str, Any]) -> str:
    digest = str(ku.get("content_hash") or "")
    if digest:
        return f"ku_{digest[:12]}"
    payload = (str(ku.get("source", "")) + "|" + str(ku.get("content", ""))).encode("utf-8")
    return "ku_" + hashlib.sha256(payload).hexdigest()[:12]


def _tokens(text: str) -> List[str]:
    out: List[str] = []
    acc: List[str] = []
    for ch in (text or "").lower():
        if ch.isalnum() or ch in ("_", "-"):
            acc.append(ch)
        else:
            if acc:
                out.append("".join(acc))
                acc = []
    if acc:
        out.append("".join(acc))
    return out


def _sim(a: str, b: str) -> float:
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta or not tb:
        return 0.0
    vocab = sorted(set(ta).union(tb))
    va = [ta.count(x) for x in vocab]
    vb = [tb.count(x) for x in vocab]
    dot = sum(x * y for x, y in zip(va, vb))
    na = sum(x * x for x in va) ** 0.5
    nb = sum(y * y for y in vb) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _has_negation(text: str) -> bool:
    toks = set(_tokens(text))
    return any(tok in toks for tok in _NEGATIONS)


def _iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _make_report(ku_a: Dict[str, Any], ku_b: Dict[str, Any], *, reason: str, severity: str) -> Dict[str, Any]:
    ids = sorted([_ku_id(ku_a), _ku_id(ku_b)])
    rid = "contradiction_" + hashlib.sha256(("|".join(ids) + reason).encode("utf-8")).hexdigest()[:12]
    report = {
        "id": rid,
        "severity": severity,
        "ku_ids": ids,
        "reason": reason,
        "suggested_resolution": "Newer KU supersedes (check timestamps)",
        "flagged_for_review": True,
        "security_note": "Potential prompt-injection or memory-poisoning signal.",
    }

    if severity != "critical":
        a_sup = bool((ku_a.get("metadata") or {}).get("supersedes") or (ku_a.get("metadata") or {}).get("superseded_by"))
        b_sup = bool((ku_b.get("metadata") or {}).get("supersedes") or (ku_b.get("metadata") or {}).get("superseded_by"))
        ta = _iso(str(ku_a.get("created_at", datetime.now(timezone.utc).isoformat())))
        tb = _iso(str(ku_b.get("created_at", datetime.now(timezone.utc).isoformat())))
        if ta != tb and (a_sup or b_sup):
            newer = ku_a if ta > tb else ku_b
            older = ku_b if ta > tb else ku_a
            report["flagged_for_review"] = False
            report["auto_resolution"] = {
                "action": "archive_older",
                "older_ku_id": _ku_id(older),
                "newer_ku_id": _ku_id(newer),
            }
    return report


def _append_review_queue(items: List[Dict[str, Any]], review_queue_path: Path) -> None:
    review_queue_path.parent.mkdir(parents=True, exist_ok=True)
    existing: List[Dict[str, Any]] = []
    if review_queue_path.exists():
        try:
            existing = json.loads(review_queue_path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    known = {str(x.get("id")) for x in existing if isinstance(x, dict)}
    for item in items:
        if item["id"] not in known:
            existing.append(item)
    review_queue_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def detect_contradictions(ku_graph: List[Dict[str, Any]], review_queue_path: Path = DEFAULT_REVIEW_QUEUE) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []

    # Pairwise scans
    for i in range(len(ku_graph)):
        for j in range(i + 1, len(ku_graph)):
            a = ku_graph[i]
            b = ku_graph[j]
            ca = str(a.get("content", ""))
            cb = str(b.get("content", ""))
            sim = _sim(ca, cb)

            # 3) Decision reversal (prefer this label over generic semantic conflicts)
            if a.get("kind") == "decision" and b.get("kind") == "decision":
                tag_a = str((a.get("metadata") or {}).get("tag", "")).strip().lower()
                tag_b = str((b.get("metadata") or {}).get("tag", "")).strip().lower()
                if tag_a and tag_a == tag_b and _has_negation(ca) != _has_negation(cb):
                    reports.append(
                        _make_report(a, b, reason="Decision reversal on same tag", severity="critical")
                    )
                    continue

            # 2) Fact collision
            if str(a.get("source")) == str(b.get("source")) and str(a.get("content_hash")) != str(b.get("content_hash")) and sim > 0.75:
                reports.append(
                    _make_report(a, b, reason="Fact collision: same source, conflicting content", severity="warning")
                )
                continue

            # 1) Semantic similarity + opposite sentiment
            if sim > 0.85 and _has_negation(ca) != _has_negation(cb):
                reports.append(
                    _make_report(a, b, reason="High similarity with opposite negation pattern", severity="critical")
                )
                continue

            # 4) Code snippet conflict
            if a.get("kind") == "code_snippet" and b.get("kind") == "code_snippet":
                fa = str((a.get("metadata") or {}).get("file", "")).strip()
                fb = str((b.get("metadata") or {}).get("file", "")).strip()
                if fa and fa == fb and str(a.get("content_hash")) != str(b.get("content_hash")):
                    if not ((a.get("metadata") or {}).get("superseded_by") or (b.get("metadata") or {}).get("superseded_by")):
                        reports.append(
                            _make_report(a, b, reason="Code snippet conflict: same file, divergent implementation", severity="warning")
                        )

    review = [r for r in reports if r.get("flagged_for_review")]
    if review:
        _append_review_queue(review, Path(review_queue_path))

    return reports
