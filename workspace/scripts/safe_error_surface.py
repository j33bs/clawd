#!/usr/bin/env python3
"""Safe error surface + redaction helpers for gateway adapters."""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Callable

SAFE_DEBUG_SUMMARY = {
    "timeout",
    "rate_limit",
    "provider_unavailable",
    "network_error",
    "validation_error",
    "internal_error",
}

_SECRET_PATTERNS = [
    re.compile(r"(authorization\s*:\s*bearer\s+)[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+\-/=]{8,}\b"),
    re.compile(r"\b(sk|gsk|xoxb|xoxp)-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"((?:api[_-]?key|token|secret|password)\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
]


def next_request_id(prefix: str = "req") -> str:
    head = re.sub(r"[^a-z0-9_-]", "", str(prefix or "req").lower()) or "req"
    return f"{head}-{int(time.time() * 1000):x}-{uuid.uuid4().hex[:8]}"


def _redact_text(value: Any) -> str:
    text = str(value or "")
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("((?:api"):
            text = pattern.sub(r"\1<redacted>", text)
        elif "authorization" in pattern.pattern.lower():
            text = pattern.sub(r"\1<redacted>", text)
        else:
            text = pattern.sub("<redacted-token>", text)
    text = re.sub(r"(cookie\s*:\s*)([^\r\n]+)", r"\1<redacted>", text, flags=re.IGNORECASE)
    text = re.sub(r"(set-cookie\s*:\s*)([^\r\n]+)", r"\1<redacted>", text, flags=re.IGNORECASE)
    return text


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if value is None:
        return None
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if re.search(r"authorization|cookie|token|secret|password|api[_-]?key", str(key), re.IGNORECASE):
                out[str(key)] = "<redacted>"
            else:
                out[str(key)] = redact(item)
        return out
    return value


def create_safe_error_envelope(
    *,
    public_message: str = "Request failed. Please retry shortly.",
    error_code: str = "gateway_error",
    request_id: str | None = None,
    occurred_at: str | None = None,
    log_ref: str | None = None,
    debug_summary: str | None = None,
) -> dict[str, Any]:
    summary = str(debug_summary or "").strip().lower()
    return {
        "public_message": str(public_message),
        "error_code": str(error_code),
        "request_id": str(request_id or next_request_id("err")),
        "occurred_at": occurred_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "log_ref": log_ref or "check local gateway logs with request_id",
        "debug_summary": summary if summary in SAFE_DEBUG_SUMMARY else None,
    }


def adapter_public_error(envelope: dict[str, Any]) -> dict[str, str]:
    return {
        "public_message": str(envelope.get("public_message", "")),
        "error_code": str(envelope.get("error_code", "gateway_error")),
        "request_id": str(envelope.get("request_id") or next_request_id("err")),
    }


def format_adapter_public_error(envelope: dict[str, Any]) -> str:
    safe = adapter_public_error(envelope)
    return f"{safe['public_message']}\nerror_code: {safe['error_code']}\nrequest_id: {safe['request_id']}"


class RedactedGatewayLogger:
    """Small logger wrapper that enforces redaction before writing."""

    def __init__(self, sink: Callable[[dict[str, Any]], None] | None = None):
        self._sink = sink or (lambda entry: None)

    def log(self, *, event: str, detail: dict[str, Any] | None = None, level: str = "info") -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": level,
            "event": str(event),
            "detail": redact(detail or {}),
        }
        self._sink(entry)
