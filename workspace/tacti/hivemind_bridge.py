"""Bridge helpers for TACTI(C)-R <-> HiveMind context operations."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class MemoryEntry:
    kind: str
    source: str
    agent_scope: str
    score: int
    created_at: str
    content: str
    metadata: Dict[str, Any]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _memory_tool_path() -> Path:
    return _repo_root() / "scripts" / "memory_tool.py"


def hivemind_query(topic: str, agent: str = "main", limit: int = 5) -> List[MemoryEntry]:
    tool = _memory_tool_path()
    if not tool.exists():
        return []

    cmd = [
        "python3",
        str(tool),
        "query",
        "--agent",
        str(agent),
        "--q",
        str(topic),
        "--limit",
        str(max(1, int(limit))),
        "--json",
    ]
    try:
        proc = subprocess.run(cmd, cwd=str(_repo_root()), capture_output=True, text=True, check=False, timeout=10)
    except Exception:
        return []

    if proc.returncode != 0:
        return []

    try:
        payload = json.loads(proc.stdout or "{}")
    except Exception:
        return []

    rows = payload.get("results", [])
    out: List[MemoryEntry] = []
    if not isinstance(rows, list):
        return out

    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            MemoryEntry(
                kind=str(row.get("kind", "")),
                source=str(row.get("source", "")),
                agent_scope=str(row.get("agent_scope", "shared")),
                score=int(row.get("score", 0) or 0),
                created_at=str(row.get("created_at", "")),
                content=str(row.get("content", "")),
                metadata=row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {},
            )
        )
    return out


def hivemind_store(entry: Dict[str, Any]) -> bool:
    tool = _memory_tool_path()
    if not tool.exists():
        return False

    kind = str(entry.get("kind", "fact"))
    content = str(entry.get("content", "")).strip()
    if not content:
        return False

    cmd = [
        "python3",
        str(tool),
        "store",
        "--kind",
        kind,
        "--content",
        content,
        "--source",
        str(entry.get("source", "tacti_cr")),
        "--agent-scope",
        str(entry.get("agent_scope", "main")),
        "--json",
    ]

    ttl_days = entry.get("ttl_days")
    if ttl_days is not None:
        cmd.extend(["--ttl-days", str(int(ttl_days))])

    try:
        proc = subprocess.run(cmd, cwd=str(_repo_root()), capture_output=True, text=True, check=False, timeout=10)
    except Exception:
        return False

    if proc.returncode != 0:
        return False

    try:
        payload = json.loads(proc.stdout or "{}")
    except Exception:
        return False

    return bool(payload.get("stored"))
