from __future__ import annotations

from pathlib import Path
from typing import Any

from .message import MESSAGE_HASH_VERSION_V2, canonical_message_hash_v2
from .session import TeamChatSession

try:
    from witness_ledger import commit as witness_commit
except Exception:  # pragma: no cover
    witness_commit = None


class TeamChatOrchestrator:
    """Deterministic round-robin orchestrator for Team Chat v1."""

    def __init__(
        self,
        *,
        session: TeamChatSession,
        router: Any,
        witness_enabled: bool = False,
        witness_ledger_path: Path | None = None,
        context_window: int = 12,
    ):
        self.session = session
        self.router = router
        self.witness_enabled = bool(witness_enabled)
        self.witness_ledger_path = Path(witness_ledger_path) if witness_ledger_path else (
            self.session.repo_root / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
        )
        self.context_window = max(2, int(context_window))

    def _build_prompt(self, agent: str) -> str:
        rows = self.session.recent(self.context_window)
        transcript = []
        for row in rows:
            role = str(row.get("role", "unknown"))
            content = str(row.get("content", ""))
            transcript.append(f"{role}: {content}")
        transcript_text = "\n".join(transcript)
        return (
            f"You are {agent}. Team Chat turn-based collaboration is active.\n"
            f"Respond concisely and constructively.\n\n"
            f"{transcript_text}"
        ).strip()

    @staticmethod
    def _extract_route(route_result: dict[str, Any] | None) -> dict[str, Any]:
        row = dict(route_result or {})
        return {
            "provider": row.get("provider"),
            "model": row.get("model"),
            "reason_code": row.get("reason_code"),
            "attempts": row.get("attempts"),
        }

    def _emit_witness(self, *, turn: int, agent: str, route: dict[str, Any], message_row: dict[str, Any]) -> None:
        if not self.witness_enabled or not callable(witness_commit):
            return
        record = {
            "event": "teamchat_turn",
            "session_id": self.session.session_id,
            "turn": int(turn),
            "agent": str(agent),
            "route": dict(route or {}),
            "message_hash_version": MESSAGE_HASH_VERSION_V2,
            "message_hash": canonical_message_hash_v2(
                message_row,
                session_id=self.session.session_id,
                turn=int(turn),
            ),
            "ts": str(message_row.get("ts", "")),
        }
        witness_commit(record=record, ledger_path=str(self.witness_ledger_path))

    def run_cycle(self, *, user_message: str, max_turns: int) -> dict[str, Any]:
        if not str(user_message or "").strip():
            return {"ok": False, "reason": "empty_user_message", "replies": []}

        self.session.append_user(str(user_message))
        replies = []
        last_role = "user"
        target_turns = min(len(self.session.agents), max(1, int(max_turns)))
        for _ in range(target_turns):
            agent = self.session.next_agent(last_role)
            intent = f"teamchat:{agent}"
            payload = {"prompt": self._build_prompt(agent)}
            context = {
                "agent_id": agent,
                "teamchat_session_id": self.session.session_id,
                "teamchat_turn": self.session.turn + 1,
                "input_text": str(user_message),
            }
            result = self.router.execute_with_escalation(intent, payload, context_metadata=context)
            route = self._extract_route(result if isinstance(result, dict) else {})
            content = str((result or {}).get("text", ""))
            if not content:
                content = f"[{agent}] no response"
            row = self.session.append_agent(agent=agent, content=content, route=route, meta={"intent": intent})
            self._emit_witness(turn=self.session.turn, agent=agent, route=route, message_row=row)
            last_role = str(row.get("role", ""))
            replies.append(row)

        return {"ok": True, "session_id": self.session.session_id, "replies": replies, "turns": len(replies)}


__all__ = ["TeamChatOrchestrator"]
