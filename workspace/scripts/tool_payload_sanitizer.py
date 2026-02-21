"""Dali tool payload sanitizer.

Canonical invariant:
- If tools are absent/empty/invalid => omit both `tools` and `tool_choice`.
- If provider does not explicitly support tool calls => omit both keys.
"""

from __future__ import annotations

from typing import Any


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

