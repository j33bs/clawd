"""Weekly evolution report loading and generation helpers."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
EVOLUTION_ROOT = REPO_ROOT / "workspace" / "evolution"
WEEKLY_TEMPLATE_PATH = EVOLUTION_ROOT / "weekly-template.md"
WEEKLY_GENERATOR_PATH = REPO_ROOT / "workspace" / "scripts" / "generate_weekly_evolution.py"
WEEKLY_SERVICE_PATH = REPO_ROOT / "workspace" / "systemd" / "openclaw-weekly-evolution.service"
WEEKLY_TIMER_PATH = REPO_ROOT / "workspace" / "systemd" / "openclaw-weekly-evolution.timer"


def _trim(text: Any, limit: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "…"


def _markdown_section(text: str, heading: str) -> str:
    lines = str(text or "").splitlines()
    start = None
    level = None
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line.startswith("#"):
            continue
        hashes = len(line) - len(line.lstrip("#"))
        title = line[hashes:].strip()
        if title == heading:
            start = idx + 1
            level = hashes
            break
    if start is None or level is None:
        return ""
    end = len(lines)
    for idx in range(start, len(lines)):
        line = lines[idx].strip()
        if not line.startswith("#"):
            continue
        hashes = len(line) - len(line.lstrip("#"))
        if hashes <= level:
            end = idx
            break
    return "\n".join(lines[start:end]).strip()


def _markdown_items(section: str, *, ordered: bool | None = None) -> list[str]:
    rows: list[str] = []
    for raw_line in str(section or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        is_bullet = line.startswith("- ")
        is_ordered = bool(re.match(r"^\d+\.\s+", line))
        if ordered is True and not is_ordered:
            continue
        if ordered is False and not is_bullet:
            continue
        if not is_bullet and not is_ordered:
            continue
        cleaned = line[2:] if is_bullet else re.sub(r"^\d+\.\s+", "", line)
        rows.append(_trim(cleaned, limit=220))
    return rows


def _report_files() -> list[Path]:
    if not EVOLUTION_ROOT.exists():
        return []
    files = [
        path
        for path in EVOLUTION_ROOT.glob("*.md")
        if path.name != WEEKLY_TEMPLATE_PATH.name and re.match(r"^\d{4}-W\d{2}\.md$", path.name)
    ]
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)


def latest_report_path() -> Path | None:
    files = _report_files()
    return files[0] if files else None


def parse_report(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {
            "status": "backlog",
            "scheduler_configured": WEEKLY_SERVICE_PATH.exists() and WEEKLY_TIMER_PATH.exists(),
            "generator_configured": WEEKLY_GENERATOR_PATH.exists(),
            "template_present": WEEKLY_TEMPLATE_PATH.exists(),
            "latest_report_path": "",
            "wins": [],
            "regressions": [],
            "upgrades": [],
            "human_benefit_signals": [],
            "guardrail_debt": [],
            "next_experiments": [],
            "notes_excerpt": "",
        }

    text = path.read_text(encoding="utf-8", errors="ignore")
    week_of = ""
    generated = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("**Week of:**"):
            week_of = line.partition("**Week of:**")[2].strip()
        elif line.startswith("**Generated:**"):
            generated = line.partition("**Generated:**")[2].strip()

    wins = _markdown_items(_markdown_section(text, "Wins"), ordered=False)
    regressions = _markdown_items(_markdown_section(text, "Regressions"), ordered=False)
    upgrades = _markdown_items(_markdown_section(text, "Top 3 Upgrades"), ordered=True)
    human_benefit_signals = _markdown_items(_markdown_section(text, "Human Benefit Signals"), ordered=False)
    guardrail_debt = _markdown_items(_markdown_section(text, "Guardrail Debt"), ordered=False)
    next_experiments = _markdown_items(_markdown_section(text, "Next Experiments"), ordered=True)
    notes = _markdown_section(text, "Notes")

    return {
        "status": "active",
        "scheduler_configured": WEEKLY_SERVICE_PATH.exists() and WEEKLY_TIMER_PATH.exists(),
        "generator_configured": WEEKLY_GENERATOR_PATH.exists(),
        "template_present": WEEKLY_TEMPLATE_PATH.exists(),
        "latest_report_path": str(path),
        "week_of": week_of,
        "generated_at": generated,
        "wins": wins,
        "regressions": regressions,
        "upgrades": upgrades,
        "human_benefit_signals": human_benefit_signals,
        "guardrail_debt": guardrail_debt,
        "next_experiments": next_experiments,
        "notes_excerpt": _trim(notes, limit=280),
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def load_weekly_evolution_summary() -> dict[str, Any]:
    return parse_report(latest_report_path())


def generate_weekly_evolution() -> dict[str, Any]:
    if not WEEKLY_GENERATOR_PATH.exists():
        raise FileNotFoundError(f"Weekly evolution generator not found: {WEEKLY_GENERATOR_PATH}")
    completed = subprocess.run(
        ["python3", str(WEEKLY_GENERATOR_PATH)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=20.0,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "generator exited non-zero"
        raise RuntimeError(detail)

    summary = load_weekly_evolution_summary()
    summary["generator_stdout"] = _trim(completed.stdout, limit=220)
    return summary


def weekly_evolution_status_signals() -> dict[str, Any]:
    summary = load_weekly_evolution_summary()
    return {
        "has_weekly_evolution_report": bool(summary.get("latest_report_path")),
        "has_weekly_evolution_scheduler": bool(summary.get("scheduler_configured")),
        "has_weekly_evolution_generator": bool(summary.get("generator_configured")),
        "has_weekly_evolution_template": bool(summary.get("template_present")),
    }
