from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from ..store import HiveMindStore
from .utils import get_all_units_cached

REPO_ROOT = Path(__file__).resolve().parents[4]
DIGEST_DIR = REPO_ROOT / "workspace" / "hivemind" / "digests"


def _parse_period(period: str) -> timedelta:
    p = str(period).strip().lower()
    if p.endswith("d"):
        return timedelta(days=int(p[:-1]))
    if p.endswith("h"):
        return timedelta(hours=int(p[:-1]))
    return timedelta(days=7)


def _iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _summarize_group(rows: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for row in rows[:10]:
        content = str(row.get("content", "")).strip().splitlines()
        first = content[0] if content else ""
        if len(first) > 140:
            first = first[:137] + "..."
        lines.append(f"- {first}")
    return lines


def generate_cross_agent_summary(
    period: str = "7d",
    store: HiveMindStore | None = None,
    *,
    units: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    store = store or HiveMindStore()
    now = datetime.now(timezone.utc)
    since = now - _parse_period(period)

    if units is None:
        units, _meta = get_all_units_cached(store, ttl_seconds=60)
    shared = []
    for row in units:
        if str(row.get("agent_scope")) != "shared":
            continue
        try:
            created = _iso(str(row.get("created_at")))
        except Exception:
            continue
        if created >= since:
            shared.append(row)

    decisions = [r for r in shared if str(r.get("kind")) == "decision"]
    lessons = [r for r in shared if str(r.get("kind")) == "lesson"]
    code_snippets = [r for r in shared if str(r.get("kind")) == "code_snippet"]

    start = since.strftime("%b %d")
    end = now.strftime("%b %d, %Y")
    lines = [
        f"## HiveMind Digest ({start} - {end})",
        "",
        "### Decisions (Shared)",
    ]
    lines.extend(_summarize_group(decisions) or ["- No shared decisions captured."])
    lines.extend(["", "### Code Snippets (Shared)"])
    lines.extend(_summarize_group(code_snippets) or ["- No shared code snippets captured."])
    lines.extend(["", "### Lessons (Shared)"])
    lines.extend(_summarize_group(lessons) or ["- No shared lessons captured."])

    markdown = "\n".join(lines).rstrip() + "\n"
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DIGEST_DIR / f"{now.strftime('%Y%m%d')}.md"
    out_path.write_text(markdown, encoding="utf-8")

    return {
        "period": period,
        "path": str(out_path),
        "counts": {
            "shared": len(shared),
            "decisions": len(decisions),
            "code_snippets": len(code_snippets),
            "lessons": len(lessons),
        },
        "markdown": markdown,
    }
