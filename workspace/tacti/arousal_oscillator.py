"""Circadian arousal oscillator with learned hourly histogram blending."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

from .config import get_float, get_time_zone, is_enabled


TIME_PATTERNS = [
    re.compile(r"\b(?P<h>\d{2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?\b"),
    re.compile(r"\[(?P<h>\d{1,2}):(?P<m>\d{2})\]"),
    re.compile(r"\b(?P<iso>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:?\d{2})?)\b"),
]


@dataclass
class OscillatorExplain:
    baseline: float
    learned: float
    multiplier: float
    bins_used: int


class ArousalOscillator:
    def __init__(self, *, repo_root: Path | None = None, timezone_name: str | None = None):
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[2])
        self.timezone_name = timezone_name or get_time_zone()
        self.alpha = get_float("arousal_alpha", 0.4, clamp=(0.0, 1.0))
        self.threshold = get_float("arousal_suppress_threshold", 0.35, clamp=(0.0, 1.0))

    def _tz(self):
        if ZoneInfo is None:
            return timezone.utc
        try:
            return ZoneInfo(self.timezone_name)
        except Exception:
            return timezone.utc

    def _memory_paths(self) -> Iterable[Path]:
        roots = [
            self.repo_root / "workspace" / "memory",
            self.repo_root / "nodes" / "dali" / "memory",
        ]
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.glob("*.md")):
                name = path.name
                if re.match(r"\d{4}-\d{2}-\d{2}\.md$", name):
                    yield path

    @staticmethod
    def _baseline_curve(hour: int) -> float:
        # Two Gaussian peaks around 10 and 15 local time.
        p1 = math.exp(-((hour - 10.0) ** 2) / (2 * 2.0 * 2.0))
        p2 = math.exp(-((hour - 15.0) ** 2) / (2 * 2.5 * 2.5))
        baseline = 0.20 + 0.45 * p1 + 0.35 * p2
        return max(0.0, min(1.0, baseline))

    def _parse_time_from_line(self, line: str, file_date: datetime | None, tz_obj) -> list[datetime]:
        out: list[datetime] = []
        for pat in TIME_PATTERNS:
            for match in pat.finditer(line):
                groups = match.groupdict()
                iso = groups.get("iso")
                if iso:
                    text = iso.replace("Z", "+00:00")
                    try:
                        dt = datetime.fromisoformat(text)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        out.append(dt.astimezone(tz_obj))
                    except Exception:
                        continue
                    continue
                if not file_date:
                    continue
                try:
                    h = int(groups.get("h", "0"))
                    m = int(groups.get("m", "0"))
                    s = int(groups.get("s") or 0)
                    dt = file_date.replace(hour=h, minute=m, second=s, tzinfo=tz_obj)
                    out.append(dt)
                except Exception:
                    continue
        return out

    def _learned_bins(self) -> tuple[list[float], int]:
        bins = [0.0] * 24
        used = 0
        tz_obj = self._tz()
        for path in self._memory_paths():
            try:
                date_part = path.stem
                file_date = datetime.strptime(date_part, "%Y-%m-%d")
            except Exception:
                file_date = None
            text = path.read_text(encoding="utf-8", errors="ignore")
            seen_hours: list[int] = []
            for line in text.splitlines():
                for dt in self._parse_time_from_line(line, file_date, tz_obj):
                    seen_hours.append(int(dt.hour))
            for hour in seen_hours:
                bins[hour] += 1.0
                used += 1

        if used <= 0:
            return [self._baseline_curve(h) for h in range(24)], 0

        max_bin = max(bins) or 1.0
        normalized = [b / max_bin for b in bins]
        return normalized, used

    def explain(self, now_dt: datetime | None = None) -> dict[str, Any]:
        now_dt = now_dt or datetime.now(timezone.utc)
        tz_now = now_dt.astimezone(self._tz())
        hour = int(tz_now.hour)
        learned_bins, used = self._learned_bins()
        baseline = self._baseline_curve(hour)
        learned = float(learned_bins[hour])
        m = (self.alpha * learned) + ((1.0 - self.alpha) * baseline)
        m = max(0.0, min(1.0, m))
        return OscillatorExplain(
            baseline=round(baseline, 6),
            learned=round(learned, 6),
            multiplier=round(m, 6),
            bins_used=int(used),
        ).__dict__

    def multiplier(self, now_dt: datetime | None = None) -> float:
        return float(self.explain(now_dt).get("multiplier", 1.0))

    def should_apply(self) -> bool:
        return is_enabled("arousal_osc")

    def should_suppress_heavy_escalation(self, now_dt: datetime | None = None) -> bool:
        return self.multiplier(now_dt) < self.threshold


__all__ = ["ArousalOscillator", "TIME_PATTERNS"]
