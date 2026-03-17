"""Source UI helpers for TeamChat deliberation cells."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.teamchat import deliberation as teamchat_deliberation

DEFAULT_ROLES = ["synthesist", "skeptic", "builder"]
DEFAULT_PARTICIPANTS = {
    "c_lawd": "synthesist",
    "dali": "skeptic",
    "codex": "builder",
}


def _trim(text: Any, limit: int = 160) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "…"


def _normalize_list(value: Any, *, limit: int = 8) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.replace("\n", ",").split(",")]
    elif isinstance(value, list):
        items = [str(part or "").strip() for part in value]
    else:
        items = []
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


def _normalize_roles(value: Any) -> list[str]:
    roles = _normalize_list(value, limit=12)
    return roles or list(DEFAULT_ROLES)


def _normalize_participants(value: Any, roles: list[str]) -> dict[str, str]:
    participants: dict[str, str] = {}
    items: list[tuple[str, str]] = []
    if isinstance(value, dict):
        items = [(str(agent or "").strip(), str(role or "").strip()) for agent, role in value.items()]
    elif isinstance(value, str):
        raw_items = [part.strip() for part in value.replace("\n", ",").split(",")]
        for item in raw_items:
            if ":" not in item:
                continue
            agent, role = item.split(":", 1)
            items.append((agent.strip(), role.strip()))

    for agent, role in items:
        if not agent:
            continue
        if not role:
            role = roles[min(len(participants), len(roles) - 1)]
        if role not in roles:
            roles.append(role)
        participants[agent] = role

    if participants:
        return participants

    normalized_defaults = dict(DEFAULT_PARTICIPANTS)
    for role in normalized_defaults.values():
        if role not in roles:
            roles.append(role)
    return normalized_defaults


def _normalize_contribution(value: dict[str, Any]) -> dict[str, Any]:
    confidence = value.get("confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else None
    except Exception:
        confidence_value = None
    return {
        "id": str(value.get("id") or ""),
        "agent_id": str(value.get("agent_id") or ""),
        "role": str(value.get("role") or ""),
        "content": str(value.get("content") or ""),
        "agrees_with": str(value.get("agrees_with") or ""),
        "disagrees_with": str(value.get("disagrees_with") or ""),
        "evidence_refs": _normalize_list(value.get("evidence_refs")),
        "confidence": confidence_value,
        "uncertainty": str(value.get("uncertainty") or ""),
        "proposed_experiment": str(value.get("proposed_experiment") or ""),
        "timestamp": str(value.get("timestamp") or ""),
    }


def _normalize_quality(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"score": 0, "coverage": {}, "gaps": []}
    coverage = value.get("coverage") if isinstance(value.get("coverage"), dict) else {}
    return {
        "score": int(value.get("score") or 0),
        "coverage": {str(key): bool(flag) for key, flag in coverage.items()},
        "gaps": [str(item) for item in value.get("gaps", []) if str(item).strip()],
    }


def _summary_row(cell: dict[str, Any]) -> dict[str, Any]:
    contributions = [
        _normalize_contribution(item)
        for item in (cell.get("contributions") or [])
        if isinstance(item, dict)
    ]
    synthesis = cell.get("synthesis") if isinstance(cell.get("synthesis"), dict) else None
    quality = _normalize_quality(cell.get("quality"))
    return {
        "id": str(cell.get("id") or ""),
        "title": str(cell.get("title") or "deliberation"),
        "prompt_excerpt": _trim(cell.get("prompt") or "", limit=220),
        "status": str(cell.get("status") or "unknown"),
        "roles": [str(role or "") for role in (cell.get("roles") or []) if str(role or "").strip()],
        "participants": {
            str(agent or ""): str(role or "")
            for agent, role in (cell.get("participants") or {}).items()
            if str(agent or "").strip()
        },
        "mission_task_id": str(cell.get("mission_task_id") or ""),
        "time_horizon": str(cell.get("time_horizon") or ""),
        "beneficiaries": _normalize_list(cell.get("beneficiaries")),
        "desired_outcome": str(cell.get("desired_outcome") or ""),
        "guardrails": _normalize_list(cell.get("guardrails")),
        "success_metrics": _normalize_list(cell.get("success_metrics")),
        "risks": _normalize_list(cell.get("risks")),
        "decision_deadline": str(cell.get("decision_deadline") or ""),
        "contribution_count": len(contributions),
        "dissent_count": len(cell.get("dissent") or []),
        "synthesis_excerpt": _trim((synthesis or {}).get("content") or "", limit=220),
        "synthesis": synthesis or None,
        "quality": quality,
        "quality_score": int(quality.get("score") or 0),
        "contributions": contributions[-5:],
        "updated_at": str(cell.get("updated_at") or ""),
        "created_at": str(cell.get("created_at") or ""),
    }


def list_deliberations(*, status: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
    rows = teamchat_deliberation.list_deliberations(status=status)
    return [_summary_row(row) for row in rows[: max(1, int(limit))] if isinstance(row, dict)]


def get_deliberation(deliberation_id: str) -> dict[str, Any] | None:
    row = teamchat_deliberation.get_deliberation(str(deliberation_id or "").strip())
    if not isinstance(row, dict):
        return None
    summary = _summary_row(row)
    summary["prompt"] = str(row.get("prompt") or "")
    summary["dissent"] = [
        {
            "from_contribution": str(item.get("from_contribution") or ""),
            "to_contribution": str(item.get("to_contribution") or ""),
            "agent_id": str(item.get("agent_id") or ""),
            "role": str(item.get("role") or ""),
        }
        for item in (row.get("dissent") or [])
        if isinstance(item, dict)
    ]
    summary["contributions"] = [
        _normalize_contribution(item)
        for item in (row.get("contributions") or [])
        if isinstance(item, dict)
    ]
    return summary


def create_deliberation(
    *,
    title: str,
    prompt: str,
    roles: Any = None,
    participants: Any = None,
    mission_task_id: str | None = None,
    time_horizon: str | None = None,
    beneficiaries: Any = None,
    desired_outcome: str | None = None,
    guardrails: Any = None,
    success_metrics: Any = None,
    risks: Any = None,
    decision_deadline: str | None = None,
) -> dict[str, Any]:
    if not str(title or "").strip():
        raise ValueError("title is required")
    if not str(prompt or "").strip():
        raise ValueError("prompt is required")
    normalized_roles = _normalize_roles(roles)
    normalized_participants = _normalize_participants(participants, normalized_roles)
    created = teamchat_deliberation.create_deliberation(
        title=str(title or "").strip(),
        prompt=str(prompt or "").strip(),
        roles=normalized_roles,
        participants=normalized_participants,
        mission_task_id=str(mission_task_id or "").strip() or None,
        time_horizon=str(time_horizon or "").strip() or None,
        beneficiaries=_normalize_list(beneficiaries),
        desired_outcome=str(desired_outcome or "").strip() or None,
        guardrails=_normalize_list(guardrails),
        success_metrics=_normalize_list(success_metrics),
        risks=_normalize_list(risks),
        decision_deadline=str(decision_deadline or "").strip() or None,
    )
    return _summary_row(created)


def add_contribution(
    deliberation_id: str,
    *,
    agent_id: str,
    role: str,
    content: str,
    agrees_with: str | None = None,
    disagrees_with: str | None = None,
    evidence_refs: Any = None,
    confidence: float | None = None,
    uncertainty: str | None = None,
    proposed_experiment: str | None = None,
) -> dict[str, Any]:
    if not str(agent_id or "").strip():
        raise ValueError("agent_id is required")
    if not str(role or "").strip():
        raise ValueError("role is required")
    if not str(content or "").strip():
        raise ValueError("content is required")
    row = teamchat_deliberation.add_contribution(
        str(deliberation_id or "").strip(),
        agent_id=str(agent_id or "").strip(),
        role=str(role or "").strip(),
        content=str(content or "").strip(),
        agrees_with=str(agrees_with or "").strip() or None,
        disagrees_with=str(disagrees_with or "").strip() or None,
        evidence_refs=_normalize_list(evidence_refs),
        confidence=confidence,
        uncertainty=str(uncertainty or "").strip() or None,
        proposed_experiment=str(proposed_experiment or "").strip() or None,
    )
    return _normalize_contribution(row)


def add_synthesis(
    deliberation_id: str,
    *,
    synthesis: str,
    dissent_noted: bool = False,
    recommended_action: str | None = None,
    confidence: float | None = None,
    risks: Any = None,
    guardrails: Any = None,
    success_metrics: Any = None,
    next_review_at: str | None = None,
) -> dict[str, Any]:
    if not str(synthesis or "").strip():
        raise ValueError("synthesis is required")
    row = teamchat_deliberation.add_synthesis(
        str(deliberation_id or "").strip(),
        synthesis=str(synthesis or "").strip(),
        dissent_noted=bool(dissent_noted),
        recommended_action=str(recommended_action or "").strip() or None,
        confidence=confidence,
        risks=_normalize_list(risks),
        guardrails=_normalize_list(guardrails),
        success_metrics=_normalize_list(success_metrics),
        next_review_at=str(next_review_at or "").strip() or None,
    )
    return _summary_row(row)


def load_deliberation_summary(limit: int = 4) -> dict[str, Any]:
    items = list_deliberations(limit=limit)
    active_count = sum(1 for item in items if str(item.get("status") or "") == "active")
    avg_quality = int(round(sum(int(item.get("quality_score") or 0) for item in items) / len(items))) if items else 0
    return {
        "items": items,
        "active_count": active_count,
        "avg_quality_score": avg_quality,
        "has_cells": bool(items) or teamchat_deliberation.DELIBERATION_PATH.exists(),
        "storage_path": str(teamchat_deliberation.DELIBERATION_PATH),
    }
