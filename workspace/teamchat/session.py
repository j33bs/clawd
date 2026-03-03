from __future__ import annotations

from pathlib import Path
from typing import Any

from .message import agent_role, make_message
from .store import TeamChatStore, default_session_path
try:
    from memory.message_hooks import build_message_event, process_message_event
except Exception:  # pragma: no cover
    build_message_event = None
    process_message_event = None


class TeamChatSession:
    """Session state + append-only message log management."""

    def __init__(
        self,
        *,
        session_id: str,
        agents: list[str],
        repo_root: Path,
        store_path: Path | None = None,
    ):
        cleaned = []
        seen = set()
        for item in agents:
            name = str(item).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)
        if not cleaned:
            raise ValueError("agents must contain at least one participant")
        self.session_id = str(session_id).strip() or "teamchat"
        self.agents = cleaned
        self.repo_root = Path(repo_root)
        self.store = TeamChatStore(Path(store_path) if store_path else default_session_path(self.repo_root, self.session_id))
        self.turn = 0

    def _track_message(self, row: dict[str, Any], *, source: str = "teamchat", tone: str | None = None) -> None:
        if not callable(build_message_event) or not callable(process_message_event):
            return
        try:
            event = build_message_event(
                session_id=self.session_id,
                role=str(row.get("role", "unknown")),
                content=str(row.get("content", "")),
                ts_utc=str(row.get("ts", "")),
                source=source,
                tone=tone,
            )
            process_message_event(event, repo_root=self.repo_root)
        except Exception:
            return

    def append_user(self, content: str) -> dict[str, Any]:
        row = make_message(role="user", content=str(content), meta={"session_id": self.session_id})
        self._track_message(row, source="teamchat", tone="unlabeled")
        self.store.append(row)
        return row

    def append_agent(
        self,
        *,
        agent: str,
        content: str,
        route: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.turn += 1
        payload_meta = dict(meta or {})
        payload_meta.setdefault("session_id", self.session_id)
        payload_meta.setdefault("turn", int(self.turn))
        payload_meta.setdefault("agent", str(agent))
        row = make_message(
            role=agent_role(agent),
            content=str(content),
            route=route or {},
            meta=payload_meta,
        )
        self._track_message(row, source="teamchat", tone=str(payload_meta.get("tone", "unlabeled")))
        self.store.append(row)
        return row

    def messages(self) -> list[dict[str, Any]]:
        return self.store.read_all()

    def recent(self, max_items: int) -> list[dict[str, Any]]:
        rows = self.messages()
        return rows[-max(1, int(max_items)) :]

    def next_agent(self, last_role: str) -> str:
        role = str(last_role or "user")
        if role == "user":
            return self.agents[0]
        if role.startswith("agent:"):
            current = role.split(":", 1)[1]
            if current in self.agents:
                idx = self.agents.index(current)
                return self.agents[(idx + 1) % len(self.agents)]
        return self.agents[0]


__all__ = ["TeamChatSession"]
