from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def canonicalize(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _last_commit(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    last = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            last = payload
    return last


def _payload_hash(seq: int, timestamp_utc: str, prev_hash: str | None, record: Dict[str, Any]) -> str:
    base = {
        "seq": int(seq),
        "timestamp_utc": str(timestamp_utc),
        "prev_hash": prev_hash,
        "record": record,
    }
    return hashlib.sha256(canonicalize(base)).hexdigest()


def commit(record: dict, ledger_path: str, timestamp_utc: str | None = None) -> dict:
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    previous = _last_commit(path)
    seq = int(previous.get("seq", 0)) + 1 if isinstance(previous, dict) else 1
    prev_hash = previous.get("hash") if isinstance(previous, dict) else None
    stamp = str(timestamp_utc or _utc_now())

    entry_record = dict(record or {})
    digest = _payload_hash(seq=seq, timestamp_utc=stamp, prev_hash=prev_hash, record=entry_record)
    entry = {
        "seq": seq,
        "timestamp_utc": stamp,
        "prev_hash": prev_hash,
        "hash": digest,
        "record": entry_record,
    }

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {
        "hash": digest,
        "prev_hash": prev_hash,
        "timestamp_utc": stamp,
        "seq": seq,
    }


def verify_chain(ledger_path: str) -> dict:
    path = Path(ledger_path)
    if not path.exists():
        return {"ok": True, "entries": 0}
    prev_hash = None
    prev_seq = 0
    entries = 0
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            return {"ok": False, "entries": entries, "error": "invalid_json", "line": idx}
        if not isinstance(row, dict):
            return {"ok": False, "entries": entries, "error": "invalid_row", "line": idx}
        seq = int(row.get("seq", 0) or 0)
        if seq != prev_seq + 1:
            return {"ok": False, "entries": entries, "error": "seq_gap", "line": idx, "seq": seq}
        record = row.get("record", {})
        if not isinstance(record, dict):
            return {"ok": False, "entries": entries, "error": "invalid_record", "line": idx}
        row_prev_hash = row.get("prev_hash")
        if row_prev_hash != prev_hash:
            return {"ok": False, "entries": entries, "error": "prev_hash_mismatch", "line": idx}
        expected = _payload_hash(seq=seq, timestamp_utc=str(row.get("timestamp_utc", "")), prev_hash=row_prev_hash, record=record)
        if str(row.get("hash", "")) != expected:
            return {"ok": False, "entries": entries, "error": "hash_mismatch", "line": idx}
        prev_hash = str(row.get("hash", ""))
        prev_seq = seq
        entries += 1
    return {"ok": True, "entries": entries, "head_hash": prev_hash}


__all__ = ["canonicalize", "commit", "verify_chain"]
