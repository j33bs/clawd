#!/usr/bin/env python3
"""Periodic distillation from memory/YYYY-MM-DD.md into MEMORY.md."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
PLACEHOLDER_RE = re.compile(r"^-\s*$")
DAILY_HEADER = "## Daily Distillations"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_date_from_name(path: Path) -> dt.date | None:
    try:
        return dt.date.fromisoformat(path.stem)
    except ValueError:
        return None


def normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def recent_daily_files(memory_dir: Path, today: dt.date, window_days: int) -> list[Path]:
    cutoff = today - dt.timedelta(days=max(1, window_days) - 1)
    files: list[Path] = []
    for candidate in sorted(memory_dir.glob("*.md")):
        date_value = parse_date_from_name(candidate)
        if date_value is None:
            continue
        if cutoff <= date_value <= today:
            files.append(candidate)
    return files


def extract_bullets(path: Path) -> list[dict]:
    section = "unclassified"
    rows: list[dict] = []
    for idx, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        line = raw.strip()
        match = SECTION_RE.match(line)
        if match:
            section = match.group(1).strip().lower()
            continue
        if not line.startswith("- "):
            continue
        if PLACEHOLDER_RE.match(line):
            continue
        text = line[2:].strip()
        if not text:
            continue
        rows.append(
            {
                "text": text,
                "key": normalize_key(text),
                "section": section,
                "source": str(path),
                "line": idx,
            }
        )
    return rows


def ensure_daily_header(memory_md: Path) -> str:
    if not memory_md.exists():
        return "# MEMORY.md - Long-Term Context\n\n" + DAILY_HEADER + "\n"
    content = memory_md.read_text(encoding="utf-8", errors="ignore")
    if DAILY_HEADER in content:
        return content
    suffix = "" if content.endswith("\n") else "\n"
    return f"{content}{suffix}\n{DAILY_HEADER}\n"


def append_daily_block(memory_md: Path, today: dt.date, bullets: list[dict], source_files: list[Path]) -> bool:
    content = ensure_daily_header(memory_md)
    block_prefix = f"### {today.isoformat()} (auto-distill)"
    if block_prefix in content:
        return False

    lines = [
        block_prefix,
        f"- Distilled at: {utc_now().isoformat().replace('+00:00', 'Z')}",
        "- Source files:",
    ]
    for item in source_files:
        lines.append(f"  - {item}")
    lines.append("- Distinct events:")
    for entry in bullets:
        lines.append(f"  - {entry['text']}")
    block = "\n".join(lines) + "\n"
    suffix = "" if content.endswith("\n") else "\n"
    memory_md.write_text(f"{content}{suffix}{block}", encoding="utf-8")
    return True


def run(repo_root: Path, *, window_days: int, max_items: int) -> dict:
    today = dt.date.today()
    memory_dir = repo_root / "memory"
    memory_md = repo_root / "MEMORY.md"
    state_path = repo_root / "workspace" / "state_runtime" / "memory" / "daily_distill_state.json"

    files = recent_daily_files(memory_dir, today, window_days)
    state = read_json(state_path, {"schema": 1, "seen": {}})
    if not isinstance(state, dict):
        state = {"schema": 1, "seen": {}}
    seen = state.get("seen")
    if not isinstance(seen, dict):
        seen = {}

    unique: dict[str, dict] = {}
    for path in files:
        for entry in extract_bullets(path):
            unique.setdefault(entry["key"], entry)

    unseen: list[dict] = []
    for key, entry in unique.items():
        if key in seen:
            continue
        unseen.append(entry)
    unseen = unseen[: max(1, max_items)]

    updated = False
    if unseen:
        updated = append_daily_block(memory_md, today, unseen, files)
        if updated:
            stamp = utc_now().isoformat().replace("+00:00", "Z")
            for entry in unseen:
                seen[entry["key"]] = stamp

    # Keep state bounded for long-running cron use.
    if len(seen) > 4000:
        ordered_keys = sorted(seen.keys(), key=lambda k: seen.get(k, ""))
        keep_keys = set(ordered_keys[-2000:])
        seen = {k: seen[k] for k in keep_keys}

    state = {
        "schema": 1,
        "updated_at": utc_now().isoformat().replace("+00:00", "Z"),
        "window_days": max(1, window_days),
        "seen": seen,
    }
    write_json(state_path, state)

    return {
        "updated": updated,
        "date": today.isoformat(),
        "source_files": [str(path) for path in files],
        "distinct_candidates": len(unique),
        "added_events": len(unseen) if updated else 0,
        "state_path": str(state_path),
        "memory_md": str(memory_md),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Distill distinct daily memory events into MEMORY.md.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--window-days", type=int, default=2)
    parser.add_argument("--max-items", type=int, default=12)
    args = parser.parse_args()

    payload = run(
        Path(args.repo_root).resolve(),
        window_days=max(1, args.window_days),
        max_items=max(1, args.max_items),
    )
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
