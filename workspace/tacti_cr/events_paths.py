from __future__ import annotations

import os
from pathlib import Path


def resolve_events_path(repo_root: Path) -> Path:
    root = Path(repo_root)
    raw = str(os.environ.get("TACTI_CR_EVENTS_PATH", "")).strip()
    if raw:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = root / candidate
        return candidate
    return root / "workspace" / "state_runtime" / "tacti_cr" / "events.jsonl"


def ensure_parent(p: Path) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)


__all__ = ["resolve_events_path", "ensure_parent"]
