#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRAILS = REPO_ROOT / "workspace" / "hivemind" / "data" / "trails.jsonl"
DEFAULT_REPORT = REPO_ROOT / "workspace" / "reports" / "trail_landscape.md"


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def load_trails(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def filter_trails(
    rows: list[dict[str, Any]],
    *,
    source: str | None = None,
    since_hours: int | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cutoff = None
    if since_hours is not None:
        cutoff = datetime.now(UTC) - timedelta(hours=max(0, int(since_hours)))
    source_norm = str(source or "").strip().lower()
    for row in rows:
        row_source = str(row.get("source") or "unknown").strip().lower()
        if source_norm and row_source != source_norm:
            continue
        if cutoff is not None:
            ts = _parse_ts(row.get("updated_at") or row.get("created_at"))
            if ts is None or ts < cutoff:
                continue
        out.append(row)
    return out


def bucket_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"hot": 0, "fading": 0, "almost_gone": 0}
    for row in rows:
        strength = float(row.get("strength", 0.0) or 0.0)
        if strength > 0.8:
            counts["hot"] += 1
        elif strength >= 0.3:
            counts["fading"] += 1
        else:
            counts["almost_gone"] += 1
    return counts


def render_landscape(rows: list[dict[str, Any]], *, source: str | None, since_hours: int | None) -> str:
    counts = bucket_counts(rows)
    lines = [
        "# Trail Landscape",
        "",
        f"- generated_utc: {datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}",
        f"- source_filter: {source or 'any'}",
        f"- since_hours: {since_hours if since_hours is not None else 'any'}",
        f"- total: {len(rows)}",
        "",
        "| bucket | rule | count |",
        "|---|---|---:|",
        f"| hot | strength > 0.8 | {counts['hot']} |",
        f"| fading | 0.3 <= strength <= 0.8 | {counts['fading']} |",
        f"| almost-gone | strength < 0.3 | {counts['almost_gone']} |",
        "",
        "## Top trails",
    ]
    top = sorted(
        rows,
        key=lambda row: (
            -float(row.get("strength", 0.0) or 0.0),
            str(row.get("updated_at", "")),
            str(row.get("trail_id", "")),
        ),
    )[:10]
    for row in top:
        lines.append(
            f"- {row.get('trail_id', '(none)')} | strength={float(row.get('strength', 0.0) or 0.0):.3f} | source={row.get('source', 'unknown')}"
        )
    if not top:
        lines.append("- (no trails)")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render trail landscape buckets from trail store")
    parser.add_argument("--trail-path", default=str(DEFAULT_TRAILS))
    parser.add_argument("--source", default="")
    parser.add_argument("--since-hours", type=int)
    parser.add_argument("--output")
    args = parser.parse_args()

    rows = load_trails(Path(args.trail_path))
    rows = filter_trails(rows, source=(args.source or None), since_hours=args.since_hours)
    rendered = render_landscape(rows, source=(args.source or None), since_hours=args.since_hours)
    print(rendered, end="")
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

