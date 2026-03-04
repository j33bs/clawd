#!/usr/bin/env python3
"""Enforce Grok-fast-only primary/fallback defaults in OpenClaw config."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CFG = Path.home() / ".openclaw" / "openclaw.json"
GROK_FAST = "xai/grok-4-1-fast"
GROK_OLD = "xai/grok" + "-4"
MINIMAX = "minimax-portal/MiniMax-M2.1"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if isinstance(value, dict):
        return value
    if value is None:
        parent[key] = {}
        return parent[key]
    raise TypeError(f"Expected object at {key}, got {type(value).__name__}")


def main() -> int:
    original = CFG.read_text(encoding="utf-8")
    pre_sha = sha256_text(original)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = CFG.with_name(f"{CFG.name}.bak.{ts}")
    backup.write_text(original, encoding="utf-8")

    cfg = json.loads(original)
    changed: list[str] = []

    agents = ensure_dict(cfg, "agents")
    defaults = ensure_dict(agents, "defaults")
    model_cfg = ensure_dict(defaults, "model")
    models = ensure_dict(defaults, "models")

    if model_cfg.get("primary") != GROK_FAST:
        model_cfg["primary"] = GROK_FAST
        changed.append("agents.defaults.model.primary")

    target_fallbacks = [MINIMAX]
    if model_cfg.get("fallbacks") != target_fallbacks:
        model_cfg["fallbacks"] = target_fallbacks
        changed.append("agents.defaults.model.fallbacks")

    if GROK_OLD in models:
        del models[GROK_OLD]
        changed.append("agents.defaults.models[xai/grok" + "-4]:removed")

    if GROK_FAST not in models or not isinstance(models.get(GROK_FAST), dict):
        models[GROK_FAST] = {}
        changed.append("agents.defaults.models[xai/grok-4-1-fast]")

    if MINIMAX not in models or not isinstance(models.get(MINIMAX), dict):
        models[MINIMAX] = {}
        changed.append("agents.defaults.models[minimax-portal/MiniMax-M2.1]")

    updated = json.dumps(cfg, indent=2) + "\n"
    CFG.write_text(updated, encoding="utf-8")
    post_sha = sha256_text(updated)

    print(f"config={CFG}")
    print(f"backup={backup}")
    print(f"sha256_pre={pre_sha}")
    print(f"sha256_post={post_sha}")
    print("changed=" + (",".join(changed) if changed else "(none)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
