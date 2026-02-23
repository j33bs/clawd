#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "workspace" / "memory" / "session_context.md"
DEFAULT_TRAILS = REPO_ROOT / "workspace" / "hivemind" / "data" / "trails.jsonl"
DEFAULT_COMMITMENTS = REPO_ROOT / "workspace" / "reports" / "commitments.json"

SOUL_CANDIDATES = [
    REPO_ROOT / "workspace" / "SOUL.md",
    REPO_ROOT / "workspace" / "governance" / "SOUL.md",
    REPO_ROOT / "SOUL.md",
]
IDENTITY_CANDIDATES = [
    REPO_ROOT / "workspace" / "IDENTITY.md",
    REPO_ROOT / "workspace" / "governance" / "IDENTITY.md",
    REPO_ROOT / "IDENTITY.md",
]

HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def extract_markdown_headings(path: Path, *, max_headings: int = 8) -> list[str]:
    headings: list[str] = []
    if not path.exists():
        return headings
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue
        title = match.group(2).strip()
        if title:
            headings.append(title)
        if len(headings) >= max_headings:
            break
    return headings


def select_top_trails_by_strength(trail_path: Path, *, k: int = 7) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not trail_path.exists():
        return rows
    for line in trail_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    rows.sort(
        key=lambda row: (
            -float(row.get("strength", 0.0) or 0.0),
            str(row.get("updated_at", "")),
            str(row.get("trail_id", "")),
        )
    )
    selected = rows[: max(1, int(k))]
    out = []
    for row in selected:
        out.append(
            {
                "trail_id": str(row.get("trail_id", "")),
                "strength": float(row.get("strength", 0.0) or 0.0),
                "source": str(row.get("source") or "unknown"),
            }
        )
    return out


def _commitments_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"count": 0, "items": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"count": 0, "items": []}
    items = payload.get("commitments", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    summary = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        summary.append(
            {
                "section": str(item.get("section_path", "")),
                "snippet": str(item.get("snippet", ""))[:140],
            }
        )
    return {"count": len(items), "items": summary}


def assemble_session_context(
    *,
    session_id: str,
    node: str,
    output_path: Path = DEFAULT_OUTPUT,
    trail_path: Path = DEFAULT_TRAILS,
    commitments_path: Path = DEFAULT_COMMITMENTS,
    top_k: int = 7,
) -> dict[str, Any]:
    soul_path = _first_existing(SOUL_CANDIDATES)
    identity_path = _first_existing(IDENTITY_CANDIDATES)
    soul_headings = extract_markdown_headings(soul_path, max_headings=6) if soul_path else []
    identity_headings = extract_markdown_headings(identity_path, max_headings=6) if identity_path else []
    trails = select_top_trails_by_strength(trail_path, k=top_k)
    commitments = _commitments_summary(commitments_path)

    lines = [
        "# Session Context",
        "",
        f"- timestamp_utc: {_utc_now()}",
        f"- session_id: {session_id}",
        f"- node: {node}",
        "",
        "## SOUL headings",
    ]
    lines.extend([f"- {h}" for h in soul_headings] or ["- (none found)"])
    lines.extend(["", "## IDENTITY headings"])
    lines.extend([f"- {h}" for h in identity_headings] or ["- (none found)"])
    lines.extend(["", "## Top trails (by strength)"])
    lines.extend(
        [f"- {item['trail_id']} (strength={item['strength']:.3f}, source={item['source']})" for item in trails]
        or ["- (none found)"]
    )
    lines.extend(["", "## Commitments summary"])
    lines.append(f"- total_commitments: {int(commitments['count'])}")
    for item in commitments["items"]:
        lines.append(f"- {item['section']}: {item['snippet']}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "output_path": str(output_path),
        "session_id": session_id,
        "top_k": int(top_k),
        "trail_count": len(trails),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build compact session orientation context")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--node", default=os.environ.get("OPENCLAW_NODE_ID", "Dali/C_Lawd"))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--trail-path", default=str(DEFAULT_TRAILS))
    parser.add_argument("--commitments-path", default=str(DEFAULT_COMMITMENTS))
    parser.add_argument("--top-k", type=int, default=int(os.environ.get("OPENCLAW_SESSION_CONTEXT_TOP_K", "7")))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = assemble_session_context(
        session_id=str(args.session_id),
        node=str(args.node),
        output_path=Path(args.output_path),
        trail_path=Path(args.trail_path),
        commitments_path=Path(args.commitments_path),
        top_k=max(1, int(args.top_k)),
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

