"""Three-year public-benefit planning helpers for Source UI."""

from __future__ import annotations

from typing import Any

_VALID_HORIZONS = {
    "0-6m": "0-6 months",
    "6-18m": "6-18 months",
    "18-36m": "18-36 months",
}
_VALID_EVIDENCE = {"speculative", "emerging", "operational"}
_VALID_REVERSIBILITY = {"low", "medium", "high"}
_VALID_LEVERAGE = {"workflow", "surface", "platform", "network"}
_REQUIRED_IMPACT_FIELDS = (
    "beneficiaries",
    "public_benefit_hypothesis",
    "leading_indicators",
    "guardrails",
    "time_horizon",
)
_PHASES = [
    ("0-6m", "Phase 1 - Trust foundations", "Reduce coordination friction while keeping consent and provenance explicit."),
    ("6-18m", "Phase 2 - Compounding coordination", "Turn reviewed memory and relational state into reliable, bounded leverage."),
    ("18-36m", "Phase 3 - Collective reach", "Scale the system's ability to coordinate many contributors without collapsing accountability."),
]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_list(value: Any, *, limit: int = 8) -> list[str]:
    items: list[str] = []
    if isinstance(value, str):
        items = [part.strip() for part in value.replace("\n", ",").split(",")]
    elif isinstance(value, list):
        items = [_clean(part) for part in value]
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
        if len(output) >= limit:
            break
    return output


def _normalize_choice(value: Any, allowed: set[str], fallback: str = "") -> str:
    raw = _clean(value).lower()
    return raw if raw in allowed else fallback


def _priority_points(value: Any) -> int:
    return {
        "critical": 24,
        "high": 18,
        "medium": 12,
        "low": 6,
    }.get(_clean(value).lower(), 10)


def _impact_readiness(row: dict[str, Any]) -> dict[str, Any]:
    covered = 0
    gaps: list[str] = []
    for field in _REQUIRED_IMPACT_FIELDS:
        value = row.get(field)
        if isinstance(value, list):
            present = bool(value)
        else:
            present = bool(_clean(value))
        if present:
            covered += 1
        else:
            gaps.append(field)
    total = len(_REQUIRED_IMPACT_FIELDS)
    ratio = round(covered / total, 4) if total else 0.0
    return {
        "covered": covered,
        "total": total,
        "ratio": ratio,
        "status": "ready" if ratio >= 0.8 else ("partial" if ratio >= 0.4 else "thin"),
        "gaps": gaps,
    }


def _impact_score(row: dict[str, Any]) -> int:
    readiness = row.get("impact_readiness") if isinstance(row.get("impact_readiness"), dict) else _impact_readiness(row)
    readiness_ratio = float(readiness.get("ratio", 0.0) or 0.0)
    evidence = _normalize_choice(row.get("evidence_status"), _VALID_EVIDENCE, "speculative")
    reversibility = _normalize_choice(row.get("reversibility"), _VALID_REVERSIBILITY, "medium")
    leverage = _normalize_choice(row.get("leverage"), _VALID_LEVERAGE, "workflow")
    time_horizon = _clean(row.get("time_horizon"))
    horizon_points = {
        "0-6m": 16,
        "6-18m": 12,
        "18-36m": 8,
    }.get(time_horizon, 6)
    evidence_points = {
        "operational": 12,
        "emerging": 8,
        "speculative": 4,
    }.get(evidence, 4)
    reversibility_points = {
        "high": 10,
        "medium": 6,
        "low": 2,
    }.get(reversibility, 4)
    leverage_points = {
        "network": 14,
        "platform": 12,
        "surface": 8,
        "workflow": 5,
    }.get(leverage, 5)
    coverage_points = int(round(readiness_ratio * 24))
    score = _priority_points(row.get("priority")) + horizon_points + evidence_points + reversibility_points + leverage_points + coverage_points
    return max(0, min(100, int(score)))


def _task_status_open(row: dict[str, Any]) -> bool:
    return _clean(row.get("status")).lower() not in {"done", "archived"}


def _horizon_order(value: Any) -> int:
    return {
        "0-6m": 3,
        "6-18m": 2,
        "18-36m": 1,
    }.get(_clean(value), 0)


def _top_priorities(tasks: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    active = [row for row in tasks if _task_status_open(row)] or list(tasks)
    ranked = sorted(
        active,
        key=lambda row: (
            int(row.get("impact_score", 0) or 0),
            _horizon_order(row.get("time_horizon")),
            len(row.get("guardrails") or []),
        ),
        reverse=True,
    )
    output: list[dict[str, Any]] = []
    for row in ranked[: max(1, int(limit))]:
        output.append(
            {
                "id": str(row.get("id") or ""),
                "title": str(row.get("title") or "Untitled task"),
                "priority": str(row.get("priority") or "medium"),
                "status": str(row.get("status") or "backlog"),
                "impact_score": int(row.get("impact_score") or 0),
                "time_horizon": str(row.get("time_horizon") or ""),
                "impact_vector": str(row.get("impact_vector") or ""),
                "why_now": str(row.get("public_benefit_hypothesis") or row.get("summary") or "").strip(),
                "guardrails": list(row.get("guardrails") or []),
                "beneficiaries": list(row.get("beneficiaries") or []),
                "leading_indicators": list(row.get("leading_indicators") or []),
            }
        )
    return output


def _phase_tasks(tasks: list[dict[str, Any]], horizon: str) -> list[dict[str, Any]]:
    rows = [row for row in tasks if str(row.get("time_horizon") or "") == horizon]
    if not rows and horizon == "0-6m":
        rows = sorted(tasks, key=lambda row: int(row.get("impact_score") or 0), reverse=True)[:3]
    return rows


def _build_roadmap(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    phases: list[dict[str, Any]] = []
    for horizon, label, objective in _PHASES:
        rows = _phase_tasks(tasks, horizon)
        phases.append(
            {
                "id": horizon,
                "label": label,
                "time_horizon": horizon,
                "objective": objective,
                "task_count": len(rows),
                "tasks": [
                    {
                        "id": str(row.get("id") or ""),
                        "title": str(row.get("title") or "Untitled task"),
                        "impact_score": int(row.get("impact_score") or 0),
                        "summary": str(row.get("summary") or ""),
                        "priority": str(row.get("priority") or "medium"),
                        "impact_vector": str(row.get("impact_vector") or ""),
                        "beneficiaries": list(row.get("beneficiaries") or []),
                        "guardrails": list(row.get("guardrails") or []),
                        "leading_indicators": list(row.get("leading_indicators") or []),
                    }
                    for row in rows
                ],
            }
        )
    return {
        "phases": phases,
        "summary": f"{len(phases)} phases spanning 36 months with {len(tasks)} mission tasks.",
    }


def normalize_mission_tasks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["impact_vector"] = _clean(item.get("impact_vector"))
        item["time_horizon"] = _clean(item.get("time_horizon")) if _clean(item.get("time_horizon")) in _VALID_HORIZONS else ""
        item["beneficiaries"] = _normalize_list(item.get("beneficiaries"))
        item["public_benefit_hypothesis"] = _clean(item.get("public_benefit_hypothesis"))
        item["leading_indicators"] = _normalize_list(item.get("leading_indicators"))
        item["guardrails"] = _normalize_list(item.get("guardrails"))
        item["evidence_status"] = _normalize_choice(item.get("evidence_status"), _VALID_EVIDENCE, "")
        item["reversibility"] = _normalize_choice(item.get("reversibility"), _VALID_REVERSIBILITY, "")
        item["leverage"] = _normalize_choice(item.get("leverage"), _VALID_LEVERAGE, "")
        item["impact_readiness"] = _impact_readiness(item)
        item["impact_score"] = _impact_score(item)
        tasks.append(item)
    return tasks


def build_world_better_payload(
    *,
    source_mission: dict[str, Any],
    tasks: list[dict[str, Any]],
    deliberations: dict[str, Any],
    weekly_evolution: dict[str, Any],
    context_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mission_tasks = normalize_mission_tasks(
        source_mission.get("tasks") if isinstance(source_mission.get("tasks"), list) else []
    )
    beneficiary_counts: dict[str, int] = {}
    vector_counts: dict[str, int] = {}
    guardrail_gaps: list[dict[str, Any]] = []
    ready_count = 0
    guardrail_count = 0
    metric_count = 0
    for row in mission_tasks:
        for beneficiary in row.get("beneficiaries") or []:
            beneficiary_counts[beneficiary] = beneficiary_counts.get(beneficiary, 0) + 1
        vector = str(row.get("impact_vector") or "")
        if vector:
            vector_counts[vector] = vector_counts.get(vector, 0) + 1
        readiness = row.get("impact_readiness") if isinstance(row.get("impact_readiness"), dict) else {}
        if float(readiness.get("ratio", 0.0) or 0.0) >= 0.8:
            ready_count += 1
        if row.get("guardrails"):
            guardrail_count += 1
        if row.get("leading_indicators"):
            metric_count += 1
        if readiness.get("gaps"):
            guardrail_gaps.append(
                {
                    "id": str(row.get("id") or ""),
                    "title": str(row.get("title") or "Untitled task"),
                    "missing": list(readiness.get("gaps") or []),
                }
            )

    timeline_count = len(context_packet.get("summary_lines") or []) if isinstance(context_packet, dict) else 0
    deliberation_items = deliberations.get("items") if isinstance(deliberations.get("items"), list) else []
    deliberation_scores = [
        int(item.get("quality", {}).get("score") or item.get("quality_score") or 0)
        for item in deliberation_items
        if isinstance(item, dict)
    ]
    avg_deliberation_score = int(round(sum(deliberation_scores) / len(deliberation_scores))) if deliberation_scores else 0
    roadmap = _build_roadmap(mission_tasks)
    top_priorities = _top_priorities(mission_tasks)
    scorecard = [
        {
            "label": "Impact-ready mission tasks",
            "value": f"{ready_count}/{len(mission_tasks)}" if mission_tasks else "0/0",
            "detail": "Tasks with explicit beneficiaries, hypotheses, metrics, guardrails, and horizon.",
        },
        {
            "label": "Guardrail coverage",
            "value": f"{guardrail_count}/{len(mission_tasks)}" if mission_tasks else "0/0",
            "detail": "Mission tasks that already name at least one concrete safeguard.",
        },
        {
            "label": "Metric coverage",
            "value": f"{metric_count}/{len(mission_tasks)}" if mission_tasks else "0/0",
            "detail": "Mission tasks with at least one leading indicator.",
        },
        {
            "label": "Deliberation quality",
            "value": f"{avg_deliberation_score}%",
            "detail": "Average structured-deliberation coverage score across current cells.",
        },
        {
            "label": "Context continuity lines",
            "value": str(timeline_count),
            "detail": "Compact packet lines carried across surfaces and sessions.",
        },
        {
            "label": "Weekly evolution loop",
            "value": str(weekly_evolution.get("status") or "backlog"),
            "detail": "Whether the system is currently producing a review loop instead of relying on memory alone.",
        },
    ]

    summary = (
        f"{ready_count}/{len(mission_tasks)} mission tasks currently carry explicit public-benefit scaffolding; "
        f"{len(top_priorities)} are surfaced as highest-leverage priorities for the next cycle."
        if mission_tasks
        else "No machine-readable public-benefit mission tasks are currently configured."
    )

    return {
        "status": "active" if mission_tasks else "backlog",
        "summary": summary,
        "score_method": "heuristic_public_benefit_v1",
        "scorecard": scorecard,
        "top_priorities": top_priorities,
        "roadmap": roadmap,
        "beneficiary_map": [
            {"label": key, "task_count": beneficiary_counts[key]}
            for key in sorted(beneficiary_counts)
        ],
        "impact_vectors": [
            {"label": key, "task_count": vector_counts[key]}
            for key in sorted(vector_counts)
        ],
        "guardrail_gaps": guardrail_gaps[:8],
        "three_year_outcomes": [
            row for row in (source_mission.get("three_year_outcomes") or []) if isinstance(row, dict)
        ],
        "anti_goals": [str(item) for item in (source_mission.get("anti_goals") or []) if _clean(item)],
        "decision_rules": [str(item) for item in (source_mission.get("decision_rules") or []) if _clean(item)],
        "mission_tasks": mission_tasks,
    }


def build_three_year_roadmap_markdown(payload: dict[str, Any]) -> str:
    scorecard = payload.get("scorecard") if isinstance(payload.get("scorecard"), list) else []
    top_priorities = payload.get("top_priorities") if isinstance(payload.get("top_priorities"), list) else []
    roadmap = payload.get("roadmap") if isinstance(payload.get("roadmap"), dict) else {}
    phases = roadmap.get("phases") if isinstance(roadmap.get("phases"), list) else []
    lines: list[str] = [
        "# Source World-Better Roadmap",
        "",
        str(payload.get("summary") or "").strip(),
        "",
        "## Scorecard",
        "",
    ]
    for row in scorecard:
        if not isinstance(row, dict):
            continue
        lines.append(f"- **{row.get('label', 'Signal')}:** {row.get('value', '')} - {row.get('detail', '')}")

    lines.extend(["", "## Highest-leverage next moves", ""])
    for index, row in enumerate(top_priorities[:5], start=1):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"{index}. **{row.get('title', 'Untitled task')}** ({row.get('time_horizon', 'unscheduled')}, score {row.get('impact_score', 0)}): {row.get('why_now', '')}"
        )
        if row.get("guardrails"):
            lines.append(f"   - Guardrails: {', '.join(row.get('guardrails') or [])}")
        if row.get("leading_indicators"):
            lines.append(f"   - Leading indicators: {', '.join(row.get('leading_indicators') or [])}")

    for phase in phases:
        if not isinstance(phase, dict):
            continue
        lines.extend(["", f"## {phase.get('label', 'Phase')}", "", str(phase.get('objective', '')).strip(), ""])
        for task in phase.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            lines.append(
                f"- **{task.get('title', 'Untitled task')}** - {task.get('summary', '')}"
            )
            if task.get("beneficiaries"):
                lines.append(f"  - Beneficiaries: {', '.join(task.get('beneficiaries') or [])}")
            if task.get("guardrails"):
                lines.append(f"  - Guardrails: {', '.join(task.get('guardrails') or [])}")

    anti_goals = [str(item).strip() for item in payload.get("anti_goals") or [] if str(item).strip()]
    if anti_goals:
        lines.extend(["", "## Anti-goals", ""])
        for item in anti_goals:
            lines.append(f"- {item}")

    return "\n".join(lines).rstrip() + "\n"
