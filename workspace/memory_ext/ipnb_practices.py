from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ._common import memory_ext_enabled, runtime_dir, utc_now_iso
except ImportError:  # pragma: no cover
    from _common import memory_ext_enabled, runtime_dir, utc_now_iso


def _somatic_log_path() -> Path:
    return runtime_dir("memory_ext", "somatic_log.md")


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def somatic_checkin(now: Optional[datetime] = None) -> Dict[str, Any]:
    if not memory_ext_enabled():
        return {"felt_sense": "unknown", "ready": False, "enabled": False}
    ts = utc_now_iso(now)
    felt = "clear"
    ready = True
    _append_line(_somatic_log_path(), "- {ts} felt_sense={felt} ready={ready}".format(ts=ts, felt=felt, ready=str(ready).lower()))
    return {"felt_sense": felt, "ready": ready, "enabled": True, "timestamp_utc": ts}


def mwe_activator(text: str) -> Dict[str, Any]:
    normalized = str(text or "").lower()
    cues = ["we", "together", "us", "co-regulate", "co regulate", "with you"]
    cue = next((c for c in cues if c in normalized), "")
    mode = "co_regulated" if cue else "individual"
    return {"mode": mode, "cue": cue}


def vertical_integrate(stack_level: int) -> Dict[str, Any]:
    level = max(1, min(4, int(stack_level)))
    return {"integrated": level >= 2, "level_achieved": level}


def temporal_recall(timeframe: str) -> Dict[str, Any]:
    somatic_log = _somatic_log_path()
    if not somatic_log.exists():
        return {"memory_entries": [], "themes": []}
    entries = [line.strip() for line in somatic_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    tf = str(timeframe or "").lower()
    if tf == "1_week":
        entries = entries[-7:]
    elif tf == "1_month":
        entries = entries[-30:]
    themes: List[str] = []
    if entries:
        themes.append("somatic_checkin")
    if any("ready=true" in e for e in entries):
        themes.append("readiness")
    return {"memory_entries": entries, "themes": themes}


def _main() -> int:
    parser = argparse.ArgumentParser(description="IPNB practices baseline")
    parser.add_argument("--text", default="", help="Optional text for relationship activation")
    args = parser.parse_args()
    print(somatic_checkin())
    print(mwe_activator(args.text))
    print(vertical_integrate(2))
    print(temporal_recall("all"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
