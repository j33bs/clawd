from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..store import HiveMindStore

REPO_ROOT = Path(__file__).resolve().parents[4]
ARCHIVE_DIR = REPO_ROOT / "workspace" / "hivemind" / "archive"
REVIEW_QUEUE = REPO_ROOT / "workspace" / "hivemind" / "review_queue.json"
PRUNE_LOG = REPO_ROOT / "workspace" / "hivemind" / "prune.log"
PROTECTED_KINDS = {"decision", "architecture"}


def _iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _tokenize(text: str) -> List[str]:
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
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return 0.0
    vocab = sorted(set(ta).union(tb))
    va = [ta.count(x) for x in vocab]
    vb = [tb.count(x) for x in vocab]
    dot = sum(x * y for x, y in zip(va, vb))
    na = sum(x * x for x in va) ** 0.5
    nb = sum(y * y for y in vb) ** 0.5
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def _append_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _append_review(entries: List[Dict[str, Any]]) -> None:
    REVIEW_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    current: List[Dict[str, Any]] = []
    if REVIEW_QUEUE.exists():
        try:
            current = json.loads(REVIEW_QUEUE.read_text(encoding="utf-8"))
        except Exception:
            current = []
    current.extend(entries)
    REVIEW_QUEUE.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")


def prune_expired_and_stale(dry_run: bool = False, store: HiveMindStore | None = None) -> Dict[str, Any]:
    store = store or HiveMindStore()
    now = datetime.now(timezone.utc)
    units = store.all_units()
    keep: List[Dict[str, Any]] = []
    archive_rows: List[Dict[str, Any]] = []
    deleted_rows: List[Dict[str, Any]] = []
    review_rows: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []

    # First pass rules 1-3
    for row in units:
        kind = str(row.get("kind", ""))
        created = _iso(str(row.get("created_at") or now.isoformat()))
        expires_at = row.get("expires_at")
        last_accessed = str(row.get("last_accessed_at") or row.get("created_at") or now.isoformat())
        try:
            last_ref = _iso(last_accessed)
        except Exception:
            last_ref = created
        access_count = int(row.get("access_count", 0))
        confidence = float((row.get("metadata") or {}).get("confidence", 1.0))

        # 1) TTL expiry
        if expires_at:
            try:
                exp = _iso(str(expires_at))
            except Exception:
                exp = None
            if exp and now >= exp:
                if kind in PROTECTED_KINDS:
                    review_rows.append({"reason": "protected_ttl_expired", "content_hash": row.get("content_hash")})
                    keep.append(row)
                    continue
                archive_rows.append(row)
                deleted_rows.append(row)
                actions.append({"action": "delete_ttl_expired", "content_hash": row.get("content_hash")})
                continue

        # 2) Access decay
        if access_count == 0 and created <= (now - timedelta(days=90)):
            if kind in PROTECTED_KINDS:
                review_rows.append({"reason": "protected_access_decay", "content_hash": row.get("content_hash")})
                keep.append(row)
                continue
            archive_rows.append(row)
            deleted_rows.append(row)
            actions.append({"action": "archive_access_decay", "content_hash": row.get("content_hash")})
            continue

        # 3) Confidence decay
        if confidence < 0.4 and last_ref <= (now - timedelta(days=30)):
            if kind in PROTECTED_KINDS:
                review_rows.append({"reason": "protected_low_confidence", "content_hash": row.get("content_hash")})
                keep.append(row)
                continue
            archive_rows.append(row)
            deleted_rows.append(row)
            actions.append({"action": "delete_low_confidence", "content_hash": row.get("content_hash")})
            continue

        keep.append(row)

    # 4) Duplicate merge (>0.95 same kind)
    merged_keep: List[Dict[str, Any]] = []
    skip_hashes = set()
    for i, a in enumerate(keep):
        ah = str(a.get("content_hash", ""))
        if ah in skip_hashes:
            continue
        merged = dict(a)
        merged_from: List[str] = []
        for j in range(i + 1, len(keep)):
            b = keep[j]
            bh = str(b.get("content_hash", ""))
            if bh in skip_hashes:
                continue
            if str(a.get("kind")) != str(b.get("kind")):
                continue
            if _sim(str(a.get("content", "")), str(b.get("content", ""))) > 0.95:
                if str(a.get("kind")) in PROTECTED_KINDS:
                    review_rows.append({"reason": "protected_duplicate_merge", "content_hash": bh})
                    continue
                skip_hashes.add(bh)
                merged_from.append(bh)
                archive_rows.append(b)
                actions.append({"action": "merge_duplicate", "from": bh, "into": ah})
        if merged_from:
            md = dict(merged.get("metadata") or {})
            md["merged_from"] = sorted(set(md.get("merged_from", []) + merged_from))
            merged["metadata"] = md
        merged_keep.append(merged)

    report = {
        "dry_run": dry_run,
        "deleted": len(deleted_rows),
        "archived": len(archive_rows),
        "review": len(review_rows),
        "remaining": len(merged_keep),
        "actions": actions,
    }

    log_entry = {
        "ts_utc": now.isoformat(),
        **report,
    }

    if not dry_run:
        stamp = now.strftime("%Y%m%d")
        archive_path = ARCHIVE_DIR / f"{stamp}.jsonl"
        if archive_rows:
            _append_jsonl(archive_path, archive_rows)
        if review_rows:
            _append_review(review_rows)
        store.write_units(merged_keep)
        _append_jsonl(PRUNE_LOG, [log_entry])

    return report
