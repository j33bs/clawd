#!/usr/bin/env python3
"""
Deterministic checks for intent failure taxonomy classification.
"""
import json
import tempfile
from pathlib import Path

from intent_failure_scan import find_pattern, scan_router_events


def test_reason_patterns():
    cases = {
        "telegram_not_configured: No allowed Telegram chat IDs configured": "telegram_not_configured",
        "telegram_chat_not_allowed target chat_id is not in allowlist": "telegram_chat_not_allowed",
        "telegram_chat_not_found": "telegram_chat_not_found",
        "chat not found": "telegram_chat_not_found",
        "openclaw_status_unavailable command timed out": "openclaw_status_unavailable",
    }
    for text, expected in cases.items():
        pat = find_pattern(text)
        assert pat is not None, f"pattern missing for: {text}"
        assert pat["id"] == expected, f"{text} => {pat['id']} (expected {expected})"


def test_router_reason_aggregation():
    with tempfile.TemporaryDirectory() as td:
        log_path = Path(td) / "router.jsonl"
        entries = [
            {"event": "router_fail", "detail": {"reason_code": "request_http_429"}},
            {"event": "router_escalate", "detail": {"reason_code": "request_http_429"}},
            {"event": "router_escalate", "detail": {"reason_code": "request_timeout"}},
            {"event": "router_skip", "detail": {"reason_code": "auth_login_required"}},
        ]
        with log_path.open("w", encoding="utf-8") as f:
            for row in entries:
                f.write(json.dumps(row) + "\n")
        out = scan_router_events(log_path)
        assert out["total"] == 3, out
        assert out["by_reason"].get("request_http_429") == 2, out
        assert out["by_reason"].get("request_timeout") == 1, out


def main():
    test_reason_patterns()
    test_router_reason_aggregation()
    print("ok")


if __name__ == "__main__":
    main()
