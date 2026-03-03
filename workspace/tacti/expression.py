"""Gene-expression style feature router for TACTI(C)-R features."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_float, is_enabled


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("features"), list):
        return [x for x in payload["features"] if isinstance(x, dict)]
    return []


def _cond_ok(name: str, cond: Any, context: dict[str, Any]) -> bool:
    if cond is None:
        return True
    if name == "time_of_day":
        hour = int(context.get("hour", 0))
        if isinstance(cond, dict):
            start = int(cond.get("start", 0))
            end = int(cond.get("end", 23))
            return start <= hour <= end
    if name == "budget_remaining_min":
        return float(context.get("budget_remaining", 1.0)) >= float(cond)
    if name == "local_available":
        return bool(context.get("local_available", False)) == bool(cond)
    if name == "arousal_min":
        return float(context.get("arousal", 1.0)) >= float(cond)
    if name == "valence_min":
        return float(context.get("valence", 0.0)) >= float(cond)
    if name == "valence_max":
        return float(context.get("valence", 0.0)) <= float(cond)
    return True


def compute_expression(
    now: datetime | None,
    context: dict[str, Any],
    *,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    repo_root = Path(__file__).resolve().parents[2]
    path = manifest_path or (repo_root / "workspace" / "policy" / "expression_manifest.json")
    manifest = _load_manifest(path)

    expression_enabled = is_enabled("expression_router")
    enabled: list[str] = []
    suppressed: list[str] = []
    reasons: dict[str, list[str]] = {}

    local_ctx = dict(context or {})
    local_ctx.setdefault("hour", int(now.hour))

    for item in sorted(manifest, key=lambda x: int(x.get("priority", 1000))):
        name = str(item.get("feature_name") or "").strip()
        if not name:
            continue
        if not expression_enabled:
            suppressed.append(name)
            reasons[name] = ["expression_router_disabled"]
            continue

        ok = True
        item_reasons: list[str] = []
        activation = item.get("activation_conditions", {}) or {}
        suppression = item.get("suppression_conditions", {}) or {}

        for key, cond in activation.items() if isinstance(activation, dict) else []:
            if not _cond_ok(key, cond, local_ctx):
                ok = False
                item_reasons.append(f"activation:{key}")

        for key, cond in suppression.items() if isinstance(suppression, dict) else []:
            if _cond_ok(key, cond, local_ctx):
                ok = False
                item_reasons.append(f"suppression:{key}")

        if ok:
            enabled.append(name)
            reasons[name] = ["enabled"]
        else:
            suppressed.append(name)
            reasons[name] = item_reasons or ["conditions_not_met"]

    # Global negative valence guard to prefer local/low-risk behavior.
    neg_guard = get_float("valence_negative_guard", -0.35, clamp=(-1.0, 1.0))
    if float(local_ctx.get("valence", 0.0)) <= neg_guard:
        reasons.setdefault("_global", []).append("negative_valence_guard")

    return {
        "enabled_features": enabled,
        "suppressed_features": suppressed,
        "reasons": reasons,
        "manifest_path": str(path),
    }


__all__ = ["compute_expression"]
