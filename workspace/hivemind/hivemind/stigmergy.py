"""Stigmergy coordination marks with deterministic decay/query."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _to_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _utc(now: datetime | None = None) -> str:
    dt = _to_dt(now or datetime.now(timezone.utc))
    return dt.isoformat().replace("+00:00", "Z")


class StigmergyMap:
    def __init__(self, path: Path | None = None):
        self.path = path or (Path(__file__).resolve().parents[2] / "state" / "stigmergy" / "map.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return [x for x in payload if isinstance(x, dict)]
        except Exception:
            pass
        return []

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _effective(mark: dict[str, Any], now: datetime) -> float:
        ts = _to_dt(mark.get("timestamp"))
        age_hours = max(0.0, (now - ts).total_seconds() / 3600.0)
        decay = float(mark.get("decay_rate", 0.1))
        return max(0.0, float(mark.get("intensity", 0.0)) * math.exp(-decay * age_hours))

    def deposit_mark(self, topic: str, intensity: float, decay_rate: float, deposited_by: str, now: datetime | None = None) -> dict[str, Any]:
        rows = self._read()
        rows.append(
            {
                "topic": str(topic),
                "intensity": float(intensity),
                "decay_rate": float(decay_rate),
                "deposited_by": str(deposited_by),
                "timestamp": _utc(now),
            }
        )
        self._write(rows)
        return {"ok": True, "count": len(rows), "path": str(self.path)}

    def query_marks(self, now: datetime | None = None, top_n: int = 20) -> list[dict[str, Any]]:
        now_dt = _to_dt(now or datetime.now(timezone.utc))
        scored = []
        for row in self._read():
            item = dict(row)
            item["effective_intensity"] = round(self._effective(row, now_dt), 6)
            scored.append(item)
        scored.sort(key=lambda x: (-float(x.get("effective_intensity", 0.0)), str(x.get("topic", ""))))
        return scored[: max(1, int(top_n))]

    def suggest_avoid_topics(self, now: datetime | None = None, threshold: float = 0.75) -> list[str]:
        marks = self.query_marks(now=now, top_n=100)
        return [m["topic"] for m in marks if float(m.get("effective_intensity", 0.0)) >= float(threshold)]


__all__ = ["StigmergyMap"]
