"""Team Chat package: append-only multi-agent conversational workspace."""

from .message import agent_role, canonical_message_hash, make_message
from .orchestrator import TeamChatOrchestrator
from .session import TeamChatSession
from .store import TeamChatStore, default_session_path

__all__ = [
    "TeamChatOrchestrator",
    "TeamChatSession",
    "TeamChatStore",
    "agent_role",
    "canonical_message_hash",
    "default_session_path",
    "make_message",
]
