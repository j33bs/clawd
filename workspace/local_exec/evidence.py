from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def evidence_dir(repo_root: Path) -> Path:
    path = repo_root / "workspace" / "local_exec" / "evidence"
    path.mkdir(parents=True, exist_ok=True)
    return path


def append_event(repo_root: Path, job_id: str, kind: str, payload: dict[str, Any]) -> Path:
    target = evidence_dir(repo_root) / f"{job_id}.jsonl"
    event = {
        "ts_utc": _utc_now(),
        "job_id": job_id,
        "kind": kind,
        "payload": payload,
    }
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return target


def write_summary(repo_root: Path, job_id: str, summary: str) -> Path:
    target = evidence_dir(repo_root) / f"{job_id}.md"
    target.write_text(summary, encoding="utf-8")
    return target
