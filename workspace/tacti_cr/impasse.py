"""Impasse escalation ladder with repairable collapse mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ImpasseSnapshot:
    status: str
    consecutive_failures: int
    stable_events: int
    repairable: bool
    optional_modules_enabled: bool
    retrieval_limit: int
    force_compaction: bool
    attempt_ladder: list[str]
    trigger: str


class ImpasseManager:
    def __init__(
        self,
        *,
        collapse_after: int = 3,
        clear_after_stable: int = 3,
        default_retrieval_limit: int = 6,
        collapse_retrieval_limit: int = 2,
    ) -> None:
        self.collapse_after = max(2, int(collapse_after))
        self.clear_after_stable = max(1, int(clear_after_stable))
        self.default_retrieval_limit = max(1, int(default_retrieval_limit))
        self.collapse_retrieval_limit = max(1, int(collapse_retrieval_limit))
        self.consecutive_failures = 0
        self.stable_events = 0
        self.status = "healthy"

    @staticmethod
    def _ladder() -> list[str]:
        return [
            "switch_tool_or_provider",
            "retry_with_smaller_payload",
            "request_user_input",
            "enter_repairable_collapse",
        ]

    def _snapshot(self, trigger: str) -> dict[str, Any]:
        collapsed = self.status == "collapse"
        snap = ImpasseSnapshot(
            status=self.status,
            consecutive_failures=int(self.consecutive_failures),
            stable_events=int(self.stable_events),
            repairable=bool(collapsed),
            optional_modules_enabled=not collapsed,
            retrieval_limit=self.collapse_retrieval_limit if collapsed else self.default_retrieval_limit,
            force_compaction=bool(collapsed),
            attempt_ladder=self._ladder(),
            trigger=str(trigger),
        )
        return {
            "status": snap.status,
            "consecutive_failures": snap.consecutive_failures,
            "stable_events": snap.stable_events,
            "repairable": snap.repairable,
            "optional_modules_enabled": snap.optional_modules_enabled,
            "retrieval_limit": snap.retrieval_limit,
            "force_compaction": snap.force_compaction,
            "attempt_ladder": list(snap.attempt_ladder),
            "trigger": snap.trigger,
        }

    def on_failure(self, error: str, *, context_overflow: bool = False) -> dict[str, Any]:
        self.consecutive_failures += 1
        self.stable_events = 0
        self.status = "impasse"
        if context_overflow or self.consecutive_failures >= self.collapse_after:
            self.status = "collapse"
            return self._snapshot(f"failure:{error}")
        return self._snapshot(f"impasse:{error}")

    def on_success(self) -> dict[str, Any]:
        if self.status == "collapse":
            self.stable_events += 1
            if self.stable_events >= self.clear_after_stable:
                self.status = "healthy"
                self.consecutive_failures = 0
                self.stable_events = 0
        else:
            self.status = "healthy"
            self.consecutive_failures = 0
            self.stable_events = 0
        return self._snapshot("success")


__all__ = ["ImpasseManager", "ImpasseSnapshot"]
