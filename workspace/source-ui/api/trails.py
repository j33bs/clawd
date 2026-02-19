"""Trails heatmap backend payload helper."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_marks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
    except Exception:
        pass
    return []


def trails_heatmap_payload(repo_root: Path, top_n: int = 20) -> dict[str, Any]:
    path = repo_root / "workspace" / "state" / "stigmergy" / "map.json"
    rows = _read_marks(path)
    rows.sort(key=lambda x: (-float(x.get("intensity", 0.0)), str(x.get("topic", ""))))
    top = rows[: max(1, int(top_n))]
    out = []
    for row in top:
        out.append(
            {
                "topic": str(row.get("topic", "")),
                "intensity": float(row.get("intensity", 0.0)),
                "decay_rate": float(row.get("decay_rate", 0.0)),
                "last_reinforced": str(row.get("timestamp", "")),
                "agents": [str(row.get("deposited_by", "unknown"))],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "count": len(out),
        "items": out,
    }
