from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

QUIESCE_ENV = "OPENCLAW_QUIESCE"
MEMORY_EXT_ENV = "OPENCLAW_MEMORY_EXT"


def repo_root() -> Path:
    env_root = os.getenv("OPENCLAW_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[2]


def runtime_dir(*parts: str) -> Path:
    target = repo_root() / "workspace" / "state_runtime"
    for part in parts:
        target = target / part
    return target


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def utc_now_iso(ts: Optional[datetime] = None) -> str:
    value = ts or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def env_enabled(name: str, default: str = "0") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def memory_ext_enabled() -> bool:
    return env_enabled(MEMORY_EXT_ENV, "0")


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows
