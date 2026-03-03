#!/usr/bin/env python3
"""Python-native model intent router for chat-triggered model switching."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Optional

GROK_FAST = "xai/grok-4-1-fast"
GROK_DEFAULT = "xai/grok-4"
MINIMAX = "minimax-portal/MiniMax-M2.1"

_GROK_FAST_PATTERNS = [
    re.compile(r"use grok fast", re.IGNORECASE),
    re.compile(r"\bgrok fast\b", re.IGNORECASE),
    re.compile(r"fast model", re.IGNORECASE),
    re.compile(r"switch to grok fast", re.IGNORECASE),
]
_GROK_PATTERNS = [
    re.compile(r"switch to grok", re.IGNORECASE),
    re.compile(r"use grok", re.IGNORECASE),
]
_CHEAP_PATTERNS = [
    re.compile(r"use minimax", re.IGNORECASE),
    re.compile(r"go cheap", re.IGNORECASE),
    re.compile(r"cheap mode", re.IGNORECASE),
    re.compile(r"use cheap", re.IGNORECASE),
]
_AUTO_PATTERNS = [re.compile(r"\bauto\b", re.IGNORECASE)]


def handle_model_intent(text: str) -> Optional[dict]:
    if not isinstance(text, str):
        return None
    value = text.strip()
    if not value:
        return None

    if any(rx.search(value) for rx in _GROK_FAST_PATTERNS):
        return {"action": "switch", "primary": GROK_FAST, "reason": "grok_fast"}
    if any(rx.search(value) for rx in _CHEAP_PATTERNS):
        return {"action": "switch", "primary": MINIMAX, "reason": "cheap"}
    if any(rx.search(value) for rx in _AUTO_PATTERNS):
        return {"action": "switch", "primary": GROK_DEFAULT, "reason": "auto"}
    if any(rx.search(value) for rx in _GROK_PATTERNS):
        return {"action": "switch", "primary": GROK_DEFAULT, "reason": "grok"}
    return None


def maybe_apply_model_intent(text: str) -> Optional[dict]:
    intent = handle_model_intent(text)
    if not intent:
        return None
    primary = str(intent["primary"])
    reason = str(intent["reason"])
    try:
        subprocess.run(
            ["openclaw", "config", "set", "agents.defaults.model.primary", primary],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None

    if os.environ.get("OPENCLAW_MODEL_INTENT_DEBUG") == "1":
        sys.stderr.write(f"MODEL_INTENT_SWITCH primary={primary} reason={reason}\n")
    return intent


__all__ = ["handle_model_intent", "maybe_apply_model_intent"]
