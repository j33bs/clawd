from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_session_path(repo_root: Path, session_id: str) -> Path:
    return (
        Path(repo_root)
        / "workspace"
        / "state_runtime"
        / "teamchat"
        / "sessions"
        / f"{str(session_id).strip()}.jsonl"
    )


class TeamChatStore:
    """Append-only JSONL store for Team Chat sessions."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, row: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=False) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if isinstance(payload, dict):
                out.append(payload)
        return out


__all__ = ["TeamChatStore", "default_session_path"]
