"""Dali tool payload sanitizer with optional strict bypass detection."""

from __future__ import annotations

import json
import os
import sys
from typing import Any


class ToolPayloadBypassError(RuntimeError):
    """Raised when strict mode detects invalid tool payload shape."""

    def __init__(self, provider_id: str, model_id: str, callsite_tag: str):
        self.code = "TOOL_PAYLOAD_SANITIZER_BYPASSED"
        self.provider_id = str(provider_id or "")
        self.model_id = str(model_id or "")
        self.callsite_tag = str(callsite_tag or "")
        self.remediation = (
            "payload sanitizer bypassed: ensure this request path calls "
            "enforce_tool_payload_invariant() at final dispatch."
        )
        payload = self.to_dict()
        super().__init__(json.dumps(payload, sort_keys=True))

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "callsite_tag": self.callsite_tag,
            "remediation": self.remediation,
        }


def _map_tool_support(value: Any) -> bool:
    if value is True:
        return True
    if value is False:
        return False
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    if normalized in {"native", "via_adapter", "supported", "true", "yes", "1"}:
        return True
    return False


def resolve_tool_call_capability(provider: dict | None, model_id: str | None = None) -> dict:
    """Fail-closed capability resolution for tool calling."""
    if not isinstance(provider, dict):
        return {"tool_calls_supported": False}

    models = provider.get("models")
    if isinstance(models, list):
        selected = None
        if model_id:
            for model in models:
                if isinstance(model, dict) and str(model.get("id", "")).strip() == str(model_id).strip():
                    selected = model
                    break
        if selected is not None:
            tool_support = selected.get("tool_support", selected.get("toolSupport"))
            return {"tool_calls_supported": _map_tool_support(tool_support)}
        return {"tool_calls_supported": False}

    provider_support = provider.get("tool_support", provider.get("toolSupport"))
    return {"tool_calls_supported": _map_tool_support(provider_support)}


def sanitize_tool_payload(payload: dict | None, provider_caps: dict | None = None) -> dict | None:
    if not isinstance(payload, dict):
        return payload

    next_payload = dict(payload)
    caps = provider_caps or {}
    if caps.get("tool_calls_supported") is not True:
        next_payload.pop("tools", None)
        next_payload.pop("tool_choice", None)
        return next_payload

    tools = next_payload.get("tools")
    if not isinstance(tools, list) or len(tools) == 0:
        next_payload.pop("tools", None)
        next_payload.pop("tool_choice", None)

    return next_payload


def _strict_mode_enabled() -> bool:
    value = str(os.environ.get("OPENCLAW_STRICT_TOOL_PAYLOAD", "")).strip().lower()
    return value in {"1", "true", "yes"}


def _warn(record: dict) -> None:
    print(json.dumps(record, sort_keys=True), file=sys.stderr)


def enforce_tool_payload_invariant(
    payload: dict | None,
    provider_caps: dict | None,
    *,
    provider_id: str,
    model_id: str,
    callsite_tag: str,
) -> dict | None:
    """Final-boundary guard + sanitizer.

    Always sanitizes. In strict mode, invalid `tool_choice` without real `tools`
    raises ToolPayloadBypassError instead of silently continuing.
    """
    if not isinstance(payload, dict):
        return payload

    has_tool_choice = "tool_choice" in payload
    tools = payload.get("tools")
    has_nonempty_tools = isinstance(tools, list) and len(tools) > 0
    invalid_auto_shape = has_tool_choice and not has_nonempty_tools

    if invalid_auto_shape:
        if _strict_mode_enabled():
            raise ToolPayloadBypassError(provider_id=provider_id, model_id=model_id, callsite_tag=callsite_tag)
        _warn(
            {
                "level": "warn",
                "event": "tool_payload_sanitized_after_invalid_shape",
                "provider_id": str(provider_id or ""),
                "model_id": str(model_id or ""),
                "callsite_tag": str(callsite_tag or ""),
                "message": "payload sanitizer bypassed; stripped invalid tool_choice/tools shape",
            }
        )

    return sanitize_tool_payload(payload, provider_caps)
