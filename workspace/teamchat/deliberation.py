"""
Deliberation Cell Module

Provides structured multi-agent deliberation with:
- Explicit roles for participants
- Contribution tracking with role attribution
- Dissent (disagreement) recording
- Synthesis generation
- Public-benefit metadata, guardrails, and metrics
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TEAMCHAT_ROOT = Path(__file__).parent
DELIBERATION_PATH = TEAMCHAT_ROOT / "deliberations"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_string_list(value: Any, *, limit: int = 8) -> list[str]:
    items: list[str] = []
    if isinstance(value, str):
        items = [part.strip() for part in value.replace("\n", ",").split(",")]
    elif isinstance(value, list):
        items = [_clean(part) for part in value]
    rows: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        rows.append(item)
        if len(rows) >= limit:
            break
    return rows


def _normalize_confidence(value: Any) -> float | None:
    try:
        raw = float(value)
    except Exception:
        return None
    if raw < 0.0 or raw > 1.0:
        return None
    return round(raw, 4)


def _ensure_deliberation_dir() -> None:
    DELIBERATION_PATH.mkdir(exist_ok=True)


def _cell_path(deliberation_id: str) -> Path:
    return DELIBERATION_PATH / f"{deliberation_id}.json"


def _write_cell(cell_path: Path, payload: dict[str, Any]) -> None:
    with cell_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _read_cell(cell_path: Path) -> dict[str, Any]:
    with cell_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _quality_payload(deliberation: dict[str, Any]) -> dict[str, Any]:
    synthesis = deliberation.get("synthesis") if isinstance(deliberation.get("synthesis"), dict) else {}
    coverage = {
        "participants": bool(deliberation.get("participants")),
        "beneficiaries": bool(deliberation.get("beneficiaries")),
        "guardrails": bool(deliberation.get("guardrails")),
        "success_metrics": bool(deliberation.get("success_metrics")),
        "risks": bool(deliberation.get("risks")),
        "dissent": bool(deliberation.get("dissent")),
        "synthesis": bool(synthesis.get("content")),
        "action": bool(synthesis.get("recommended_action") or deliberation.get("desired_outcome")),
    }
    total = len(coverage)
    covered = sum(1 for value in coverage.values() if value)
    gaps = [key for key, value in coverage.items() if not value]
    return {
        "score": int(round((covered / total) * 100)) if total else 0,
        "coverage": coverage,
        "gaps": gaps,
    }


def create_deliberation(
    title: str,
    prompt: str,
    roles: list[str],
    participants: dict[str, str],
    *,
    mission_task_id: str | None = None,
    time_horizon: str | None = None,
    beneficiaries: list[str] | str | None = None,
    desired_outcome: str | None = None,
    guardrails: list[str] | str | None = None,
    success_metrics: list[str] | str | None = None,
    risks: list[str] | str | None = None,
    decision_deadline: str | None = None,
) -> dict[str, Any]:
    """Create a new deliberation cell."""
    _ensure_deliberation_dir()

    deliberation = {
        "id": f"delib_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}",
        "title": title,
        "prompt": prompt,
        "roles": roles,
        "participants": participants,
        "mission_task_id": _clean(mission_task_id),
        "time_horizon": _clean(time_horizon),
        "beneficiaries": _normalize_string_list(beneficiaries),
        "desired_outcome": _clean(desired_outcome),
        "guardrails": _normalize_string_list(guardrails),
        "success_metrics": _normalize_string_list(success_metrics),
        "risks": _normalize_string_list(risks),
        "decision_deadline": _clean(decision_deadline),
        "contributions": [],
        "dissent": [],
        "status": "active",
        "synthesis": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    deliberation["quality"] = _quality_payload(deliberation)

    cell_path = _cell_path(deliberation["id"])
    _write_cell(cell_path, deliberation)
    return deliberation


def add_contribution(
    deliberation_id: str,
    agent_id: str,
    role: str,
    content: str,
    agrees_with: str | None = None,
    disagrees_with: str | None = None,
    *,
    evidence_refs: list[str] | str | None = None,
    confidence: float | None = None,
    uncertainty: str | None = None,
    proposed_experiment: str | None = None,
) -> dict[str, Any]:
    """Add a contribution to a deliberation."""
    cell_path = _cell_path(deliberation_id)
    if not cell_path.exists():
        raise FileNotFoundError(f"Deliberation {deliberation_id} not found")

    deliberation = _read_cell(cell_path)

    contribution = {
        "id": f"c{len(deliberation['contributions']) + 1:03d}",
        "agent_id": agent_id,
        "role": role,
        "content": content,
        "agrees_with": agrees_with,
        "disagrees_with": disagrees_with,
        "evidence_refs": _normalize_string_list(evidence_refs),
        "confidence": _normalize_confidence(confidence),
        "uncertainty": _clean(uncertainty),
        "proposed_experiment": _clean(proposed_experiment),
        "timestamp": _now_iso(),
    }

    deliberation["contributions"].append(contribution)

    if disagrees_with:
        deliberation["dissent"].append(
            {
                "from_contribution": contribution["id"],
                "to_contribution": disagrees_with,
                "agent_id": agent_id,
                "role": role,
            }
        )

    deliberation["updated_at"] = _now_iso()
    deliberation["quality"] = _quality_payload(deliberation)
    _write_cell(cell_path, deliberation)
    return contribution


def add_synthesis(
    deliberation_id: str,
    synthesis: str,
    dissent_noted: bool = False,
    *,
    recommended_action: str | None = None,
    confidence: float | None = None,
    risks: list[str] | str | None = None,
    guardrails: list[str] | str | None = None,
    success_metrics: list[str] | str | None = None,
    next_review_at: str | None = None,
) -> dict[str, Any]:
    """Add synthesis to a deliberation cell."""
    cell_path = _cell_path(deliberation_id)
    if not cell_path.exists():
        raise FileNotFoundError(f"Deliberation {deliberation_id} not found")

    deliberation = _read_cell(cell_path)

    synthesis_payload = {
        "content": synthesis,
        "dissent_noted": dissent_noted,
        "recommended_action": _clean(recommended_action),
        "confidence": _normalize_confidence(confidence),
        "risks": _normalize_string_list(risks),
        "guardrails": _normalize_string_list(guardrails),
        "success_metrics": _normalize_string_list(success_metrics),
        "next_review_at": _clean(next_review_at),
        "timestamp": _now_iso(),
    }
    deliberation["synthesis"] = synthesis_payload
    if synthesis_payload["guardrails"] and not deliberation.get("guardrails"):
        deliberation["guardrails"] = list(synthesis_payload["guardrails"])
    if synthesis_payload["success_metrics"] and not deliberation.get("success_metrics"):
        deliberation["success_metrics"] = list(synthesis_payload["success_metrics"])
    if synthesis_payload["risks"] and not deliberation.get("risks"):
        deliberation["risks"] = list(synthesis_payload["risks"])
    deliberation["status"] = "complete"
    deliberation["updated_at"] = _now_iso()
    deliberation["quality"] = _quality_payload(deliberation)

    _write_cell(cell_path, deliberation)
    return deliberation


def get_deliberation(deliberation_id: str) -> dict[str, Any] | None:
    """Get a deliberation by ID."""
    cell_path = _cell_path(deliberation_id)
    if not cell_path.exists():
        return None
    payload = _read_cell(cell_path)
    payload["quality"] = _quality_payload(payload)
    return payload


def list_deliberations(status: str | None = None) -> list[dict[str, Any]]:
    """List all deliberations, optionally filtered by status."""
    if not DELIBERATION_PATH.exists():
        return []

    deliberations = []
    for cell_path in DELIBERATION_PATH.glob("*.json"):
        cell = _read_cell(cell_path)
        cell["quality"] = _quality_payload(cell)
        if status is None or cell.get("status") == status:
            deliberations.append(cell)

    return sorted(deliberations, key=lambda x: x.get("created_at", ""), reverse=True)
