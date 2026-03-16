#!/usr/bin/env python3
"""Generate the weekly evolution report for Source."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
EVOLUTION_ROOT = REPO_ROOT / "workspace" / "evolution"

if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api.portfolio import portfolio_payload  # noqa: E402


def _trim(text: Any, limit: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "..."


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _recent_done_titles(rows: list[dict[str, Any]], *, limit: int = 3) -> list[str]:
    recent: list[tuple[datetime, str]] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").strip().lower() != "done":
            continue
        timestamp = _parse_timestamp(row.get("completed_at") or row.get("updated_at"))
        if timestamp is None or timestamp < cutoff:
            continue
        title = _trim(row.get("title") or row.get("id") or "completed task", limit=120)
        reason = _trim(row.get("status_reason") or row.get("review_status_reason") or "", limit=110)
        recent.append((timestamp, f"{title}: {reason}" if reason else title))
    recent.sort(key=lambda item: item[0], reverse=True)
    seen: set[str] = set()
    output: list[str] = []
    for _, item in recent:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
        if len(output) >= limit:
            break
    return output


def _attention_rows(portfolio: dict[str, Any], *, limit: int = 3) -> list[str]:
    items: list[str] = []
    for row in portfolio.get("failed_units") or []:
        if not isinstance(row, dict):
            continue
        items.append(_trim(f"{row.get('label')}: {row.get('details') or row.get('status')}", limit=170))
    for row in portfolio.get("runtime_sources") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").strip().lower() == "healthy":
            continue
        items.append(_trim(f"{row.get('label')}: {row.get('details') or row.get('status')}", limit=170))
    for row in (portfolio.get("source_mission") or {}).get("tasks") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").strip().lower() == "done":
            continue
        items.append(_trim(f"{row.get('title')}: {row.get('status_reason') or row.get('status')}", limit=170))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _upgrade_rows(portfolio: dict[str, Any], *, limit: int = 3) -> list[str]:
    rows: list[str] = []
    mission_tasks = (portfolio.get("source_mission") or {}).get("tasks") or []
    for row in mission_tasks:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").strip().lower() == "done":
            continue
        rows.append(_trim(f"{row.get('title')}: {row.get('definition_of_done') or row.get('status_reason')}", limit=170))
    local_tasks = portfolio.get("tasks") or []
    for row in local_tasks:
        if not isinstance(row, dict) or row.get("read_only"):
            continue
        if str(row.get("status") or "").strip().lower() == "done":
            continue
        rows.append(_trim(f"{row.get('title')}: {row.get('description') or row.get('status')}", limit=170))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in rows:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _human_benefit_rows(portfolio: dict[str, Any], *, limit: int = 3) -> list[str]:
    world_better = portfolio.get("world_better") if isinstance(portfolio.get("world_better"), dict) else {}
    scorecard = world_better.get("scorecard") if isinstance(world_better.get("scorecard"), list) else []
    rows: list[str] = []
    for row in scorecard[: max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        rows.append(_trim(f"{row.get('label')}: {row.get('value')} — {row.get('detail')}", limit=180))
    return rows


def _guardrail_rows(portfolio: dict[str, Any], *, limit: int = 3) -> list[str]:
    world_better = portfolio.get("world_better") if isinstance(portfolio.get("world_better"), dict) else {}
    gaps = world_better.get("guardrail_gaps") if isinstance(world_better.get("guardrail_gaps"), list) else []
    rows: list[str] = []
    for row in gaps[: max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        missing = ", ".join(str(item) for item in row.get("missing") or [] if str(item).strip())
        rows.append(_trim(f"{row.get('title')}: missing {missing or 'explicit safeguards'}", limit=170))
    return rows


def _next_experiment_rows(portfolio: dict[str, Any], *, limit: int = 3) -> list[str]:
    world_better = portfolio.get("world_better") if isinstance(portfolio.get("world_better"), dict) else {}
    priorities = world_better.get("top_priorities") if isinstance(world_better.get("top_priorities"), list) else []
    rows: list[str] = []
    for row in priorities[: max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        why_now = row.get("why_now") or row.get("impact_vector") or row.get("status")
        rows.append(_trim(f"{row.get('title')}: {why_now}", limit=180))
    return rows


def _week_start(now: datetime) -> datetime:
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def build_report_markdown(portfolio: dict[str, Any]) -> tuple[str, Path]:
    now = datetime.now(timezone.utc)
    week_start = _week_start(now)
    week_id = f"{week_start.isocalendar().year}-W{week_start.isocalendar().week:02d}"
    report_path = EVOLUTION_ROOT / f"{week_id}.md"

    wins = _recent_done_titles(portfolio.get("tasks") or [])
    if not wins:
        wins = [_trim(f"{len(portfolio.get('components') or [])} components surfaced in the current Source snapshot.", limit=170)]

    regressions = _attention_rows(portfolio)
    if not regressions:
        regressions = ["No fresh regressions surfaced in the current weekly sweep."]

    upgrades = _upgrade_rows(portfolio)
    if not upgrades:
        upgrades = ["Keep the weekly loop running so the next upgrade list stays evidence-backed."]

    human_benefit = _human_benefit_rows(portfolio)
    if not human_benefit:
        human_benefit = ["No explicit public-benefit scorecard is available yet."]

    guardrail_debt = _guardrail_rows(portfolio)
    if not guardrail_debt:
        guardrail_debt = ["No material guardrail debt surfaced in this weekly sweep."]

    next_experiments = _next_experiment_rows(portfolio)
    if not next_experiments:
        next_experiments = ["Generate a world-better priority list so the next experiment queue is explicit."]

    notes = [
        f"Generated from Source on {now.isoformat().replace('+00:00', 'Z')}.",
        f"Open local tasks: {sum(1 for row in portfolio.get('tasks') or [] if isinstance(row, dict) and not row.get('read_only') and str(row.get('status') or '').lower() != 'done')}.",
        f"Failed units: {len(portfolio.get('failed_units') or [])}.",
        f"Runtime sources needing attention: {sum(1 for row in portfolio.get('runtime_sources') or [] if isinstance(row, dict) and str(row.get('status') or '').lower() != 'healthy')}.",
        f"World-better summary: {str((portfolio.get('world_better') or {}).get('summary') or 'not yet configured')}",
    ]

    markdown = "\n".join(
        [
            f"# Weekly Evolution Report - {week_id}",
            "",
            f"**Week of:** {week_start.date().isoformat()}",
            f"**Generated:** {now.isoformat().replace('+00:00', 'Z')}",
            "",
            "---",
            "",
            "## Wins",
            "",
            *[f"- {item}" for item in wins],
            "",
            "---",
            "",
            "## Regressions",
            "",
            *[f"- {item}" for item in regressions],
            "",
            "---",
            "",
            "## Top 3 Upgrades",
            "",
            *[f"{index}. {item}" for index, item in enumerate(upgrades[:3], start=1)],
            "",
            "---",
            "",
            "## Human Benefit Signals",
            "",
            *[f"- {item}" for item in human_benefit],
            "",
            "---",
            "",
            "## Guardrail Debt",
            "",
            *[f"- {item}" for item in guardrail_debt],
            "",
            "---",
            "",
            "## Next Experiments",
            "",
            *[f"{index}. {item}" for index, item in enumerate(next_experiments[:3], start=1)],
            "",
            "---",
            "",
            "## Notes",
            "",
            *[f"- {item}" for item in notes],
            "",
        ]
    )
    return markdown + "\n", report_path


def main() -> int:
    EVOLUTION_ROOT.mkdir(parents=True, exist_ok=True)
    portfolio = portfolio_payload()
    markdown, report_path = build_report_markdown(portfolio)
    report_path.write_text(markdown, encoding="utf-8")
    print(report_path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
