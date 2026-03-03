"""Repair strategy selection for common runtime failures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepairAction:
    action: str
    retryable: bool
    reason: str


class RepairEngine:
    def can_recover(self, error: Exception | str) -> bool:
        text = (str(error) or "").lower()
        return any(k in text for k in ("timeout", "refused", "unavailable", "overloaded", "context"))

    def repair(self, error: Exception | str) -> RepairAction:
        text = (str(error) or "").lower()

        if "timeout" in text or "aborted" in text:
            return RepairAction("retry_with_backoff", True, "transient timeout condition")
        if "context" in text or "token" in text:
            return RepairAction("compact_context_and_retry", True, "context budget exceeded")
        if "401" in text or "403" in text or "auth" in text:
            return RepairAction("request_operator_auth_refresh", False, "authentication failure")
        if "429" in text or "rate" in text:
            return RepairAction("cooldown_then_retry", True, "provider rate limited")
        if "unavailable" in text or "refused" in text:
            return RepairAction("fallback_provider", True, "upstream unavailable")

        return RepairAction("safe_reset", False, "unknown failure class")
