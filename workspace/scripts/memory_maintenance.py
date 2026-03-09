#!/usr/bin/env python3
"""Memory maintenance primitives for rotation, consolidation, indexing, snapshots, and cleanup."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PLACEHOLDER_LINE_RE = re.compile(r"^-\s*$")
SECTION_LINE_RE = re.compile(r"^##\s+(.+?)\s*$")
WEEKLY_HEADER = "## Weekly Distillations"
DAILY_HEADER = "## Daily Distillations"

SECTION_PRIORITY = {
    "key decisions": 7,
    "decisions": 7,
    "follow-ups": 6,
    "followups": 6,
    "actions": 5,
    "updates": 4,
    "context": 3,
    "morning check-in": 3,
    "morning checkins": 3,
    "afternoon heartbeats": 2,
    "heartbeats": 2,
    "notes": 2,
    "unclassified": 1,
}


def iso_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from exc


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def parse_positive_int(value: str | None, default: int, *, minimum: int = 1) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed >= minimum else default


def daily_template(target_date: dt.date, generated_at: dt.datetime | None = None) -> str:
    ts = (generated_at or utc_now()).isoformat().replace("+00:00", "Z")
    return (
        f"# Daily Memory - {target_date.isoformat()}\n\n"
        f"_Generated: {ts}_\n\n"
        "## Context\n"
        "- Session focus:\n"
        "- Key decisions:\n\n"
        "## Actions\n"
        "- \n\n"
        "## Follow-ups\n"
        "- \n"
    )


def ensure_daily_memory_file(memory_dir: Path, target_date: dt.date) -> tuple[Path, bool]:
    memory_dir.mkdir(parents=True, exist_ok=True)
    output = memory_dir / f"{target_date.isoformat()}.md"
    if output.exists():
        return output, False
    output.write_text(daily_template(target_date), encoding="utf-8")
    return output, True


def list_daily_files(memory_dir: Path) -> list[Path]:
    if not memory_dir.exists():
        return []
    return sorted(p for p in memory_dir.glob("*.md") if len(p.stem) == 10 and p.stem.count("-") == 2)


def parse_daily_file_date(path: Path) -> dt.date | None:
    try:
        return dt.date.fromisoformat(path.stem)
    except ValueError:
        return None


def read_json_file(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def extract_memory_bullets(path: Path) -> list[dict]:
    items = []
    section = "unclassified"
    for idx, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        stripped = raw.strip()
        section_match = SECTION_LINE_RE.match(stripped)
        if section_match:
            section = section_match.group(1).strip().lower()
            continue
        if not stripped.startswith("- "):
            continue
        if PLACEHOLDER_LINE_RE.match(stripped):
            continue
        text = stripped[2:].strip()
        if not text:
            continue
        items.append(
            {
                "text": text,
                "section": section,
                "source": str(path),
                "line": idx,
            }
        )
    return items


def normalize_fragment_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def normalize_section_name(name: str) -> str:
    value = re.sub(r"\s*\([^)]*\)\s*", " ", name.strip().lower())
    value = re.sub(r"[^a-z0-9\s-]", " ", value)
    return re.sub(r"\s+", " ", value).strip() or "unclassified"


def source_date_for_entry(entry: dict) -> dt.date | None:
    source = entry.get("source")
    if not isinstance(source, str) or not source:
        return None
    return parse_daily_file_date(Path(source))


def score_memory_entry(entry: dict, *, today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    text = str(entry.get("text", "")).strip()
    section = normalize_section_name(str(entry.get("section", "unclassified")))
    sources = entry.get("sources")
    if isinstance(sources, list) and sources:
        source_count = len({str(item) for item in sources})
    else:
        source_count = 1 if entry.get("source") else 0

    source_date = source_date_for_entry(entry)
    age_days = (today - source_date).days if source_date else 30
    recency_points = max(0, 7 - max(0, age_days))
    repetition_points = min(8, max(0, source_count - 1) * 3)
    action_points = 2 if any(token in text.lower() for token in ("todo", "fix", "follow-up", "follow up", "pending")) else 0
    length_points = 1 if 12 <= len(text) <= 220 else 0
    section_points = SECTION_PRIORITY.get(section, SECTION_PRIORITY["unclassified"])
    return section_points + recency_points + repetition_points + action_points + length_points


def rank_memory_entries(entries: list[dict], *, today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    ranked = []
    for entry in entries:
        score = score_memory_entry(entry, today=today)
        source_date = source_date_for_entry(entry)
        ranked.append(
            {
                **entry,
                "score": score,
                "source_date": source_date.isoformat() if source_date else "",
            }
        )
    return sorted(
        ranked,
        key=lambda item: (
            -int(item.get("score", 0)),
            -dt.date.fromisoformat(item["source_date"]).toordinal() if item.get("source_date") else 0,
            normalize_fragment_key(str(item.get("text", ""))),
        ),
        reverse=False,
    )


def inspect_daily_memory_file(path: Path) -> dict:
    content = path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    heading_count = sum(1 for line in lines if line.lstrip().startswith("#"))
    bullets = extract_memory_bullets(path)
    section_names = [normalize_section_name(item["section"]) for item in bullets]
    unique_sections = sorted(set(section_names))
    placeholder_count = sum(1 for line in lines if PLACEHOLDER_LINE_RE.match(line.strip()))
    contains_literal_escaped_newlines = "\\n" in content
    title_ok = lines[0].startswith("# Daily Memory - ") if lines else False
    required_sections = {"context", "actions", "follow-ups"}
    template_sections_present = required_sections.issubset(set(unique_sections))
    template_compliant = title_ok and template_sections_present
    machine_readable = heading_count >= 1 and len(bullets) >= 1
    return {
        "date": path.stem,
        "path": str(path),
        "line_count": len(lines),
        "word_count": len(content.split()),
        "heading_count": heading_count,
        "bullet_count": len(bullets),
        "placeholder_count": placeholder_count,
        "section_names": unique_sections,
        "template_compliant": template_compliant,
        "machine_readable": machine_readable,
        "contains_literal_escaped_newlines": contains_literal_escaped_newlines,
        "sha256": compute_sha256(path),
        "mtime": dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }


def normalize_daily_memory_file(path: Path) -> dict:
    original = path.read_text(encoding="utf-8", errors="ignore")
    normalized = original.replace("\r\n", "\n")
    changes: list[str] = []
    date_value = parse_daily_file_date(path)

    # Repair files that were written with escaped newlines as literal text.
    if "\\n" in normalized and normalized.count("\n") <= 4:
        normalized = normalized.replace("\\n", "\n")
        changes.append("decoded_escaped_newlines")

    lines = normalized.splitlines()
    expected_title = f"# Daily Memory - {date_value.isoformat()}" if date_value else ""
    if lines and expected_title and lines[0].strip() in {f"# {path.stem}", f"## {path.stem}", f"# {date_value.isoformat()}"}:
        lines[0] = expected_title
        normalized = "\n".join(lines)
        changes.append("normalized_title")
    elif not lines and expected_title:
        normalized = expected_title + "\n"
        changes.append("added_title")

    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
        changes.append("added_trailing_newline")

    changed = normalized != original
    if changed:
        path.write_text(normalized, encoding="utf-8")
    return {
        "path": str(path),
        "changed": changed,
        "changes": changes,
    }


def normalize_recent_daily_memory_files(
    memory_dir: Path,
    *,
    today: dt.date | None = None,
    window_days: int = 14,
    max_files: int = 32,
) -> dict:
    today = today or dt.date.today()
    cutoff = today - dt.timedelta(days=max(1, window_days) - 1)
    candidates = [
        path
        for path in list_daily_files(memory_dir)
        if cutoff <= (parse_daily_file_date(path) or today) <= today
    ][: max(1, max_files)]
    results = [normalize_daily_memory_file(path) for path in candidates]
    changed = [item for item in results if item["changed"]]
    return {
        "normalized_count": len(changed),
        "scanned_count": len(results),
        "changed_paths": [item["path"] for item in changed],
        "results": results,
    }


def assess_memory_health(
    memory_dir: Path,
    memory_md_path: Path,
    output_path: Path,
    *,
    today: dt.date | None = None,
    recent_days: int = 7,
) -> dict:
    today = today or dt.date.today()
    files = list_daily_files(memory_dir)
    entries = [inspect_daily_memory_file(path) for path in files]

    recent_cutoff = today - dt.timedelta(days=max(1, recent_days) - 1)
    recent_entries = [entry for entry in entries if recent_cutoff <= dt.date.fromisoformat(entry["date"]) <= today]
    present_dates = {entry["date"] for entry in recent_entries}
    expected_dates = [(recent_cutoff + dt.timedelta(days=offset)).isoformat() for offset in range(max(1, recent_days))]
    missing_recent_dates = [date_str for date_str in expected_dates if date_str not in present_dates]
    escaped_newline_files = [entry["path"] for entry in entries if entry["contains_literal_escaped_newlines"]]
    template_compliant_recent = sum(1 for entry in recent_entries if entry["template_compliant"])
    machine_readable_recent = sum(1 for entry in recent_entries if entry["machine_readable"])
    template_compliance_rate = (
        round(template_compliant_recent / len(recent_entries), 3) if recent_entries else 1.0
    )
    machine_readable_rate = (
        round(machine_readable_recent / len(recent_entries), 3) if recent_entries else 1.0
    )

    memory_md_exists = memory_md_path.exists()
    memory_md_content = memory_md_path.read_text(encoding="utf-8", errors="ignore") if memory_md_exists else ""
    has_daily_distillations = DAILY_HEADER in memory_md_content
    has_weekly_distillations = WEEKLY_HEADER in memory_md_content

    compounding_score = 100
    compounding_score -= min(45, len(missing_recent_dates) * 15)
    if not memory_md_exists:
        compounding_score -= 20
    if memory_md_exists and not has_daily_distillations:
        compounding_score -= 10
    if memory_md_exists and not has_weekly_distillations:
        compounding_score -= 10
    if escaped_newline_files:
        compounding_score -= 10
    compounding_score -= int(round((1 - machine_readable_rate) * 20))
    compounding_score = max(0, min(100, compounding_score))

    payload = {
        "generated_at": utc_now().isoformat().replace("+00:00", "Z"),
        "recent_window_days": max(1, recent_days),
        "memory_dir": str(memory_dir),
        "memory_md": str(memory_md_path),
        "daily_files_total": len(entries),
        "recent_daily_files": len(recent_entries),
        "missing_recent_dates": missing_recent_dates,
        "template_compliance_rate_recent": template_compliance_rate,
        "machine_readable_rate_recent": machine_readable_rate,
        "files_with_literal_escaped_newlines": escaped_newline_files,
        "long_term_memory": {
            "exists": memory_md_exists,
            "has_daily_distillations": has_daily_distillations,
            "has_weekly_distillations": has_weekly_distillations,
        },
        "compounding_score": compounding_score,
        "compounding_ready": (
            compounding_score >= 80
            and machine_readable_rate >= 0.85
            and not missing_recent_dates
            and not escaped_newline_files
            and has_daily_distillations
            and has_weekly_distillations
        ),
    }
    write_json_file(output_path, payload)
    return payload


def consolidate_memory_fragments(
    memory_dir: Path,
    output_path: Path,
    *,
    today: dt.date | None = None,
    window_days: int = 3,
    max_items: int = 60,
) -> dict:
    today = today or dt.date.today()
    cutoff = today - dt.timedelta(days=max(1, window_days) - 1)
    source_files = [p for p in list_daily_files(memory_dir) if (parse_daily_file_date(p) or today) >= cutoff]

    dedup = {}
    for path in source_files:
        for entry in extract_memory_bullets(path):
            key = normalize_fragment_key(entry["text"])
            existing = dedup.get(key)
            if existing is None:
                dedup[key] = {**entry, "sources": [entry["source"]]}
            else:
                if entry["source"] not in existing["sources"]:
                    existing["sources"].append(entry["source"])

    consolidated = rank_memory_entries(list(dedup.values()), today=today)[:max_items]
    payload = {
        "generated_at": utc_now().isoformat().replace("+00:00", "Z"),
        "window_days": max(1, window_days),
        "source_files": [str(p) for p in source_files],
        "consolidated_count": len(consolidated),
        "consolidated": consolidated,
    }
    previous = read_json_file(output_path, {})
    changed = (
        previous.get("source_files") != payload["source_files"]
        or previous.get("consolidated") != payload["consolidated"]
    )
    if changed:
        write_json_file(output_path, payload)
    return {
        "output_path": str(output_path),
        "changed": changed,
        "consolidated_count": len(consolidated),
        "source_files": payload["source_files"],
    }


def build_memory_index(memory_dir: Path, output_path: Path) -> dict:
    entries = [inspect_daily_memory_file(path) for path in list_daily_files(memory_dir)]

    payload = {
        "generated_at": utc_now().isoformat().replace("+00:00", "Z"),
        "memory_dir": str(memory_dir),
        "total_files": len(entries),
        "entries": entries,
    }
    write_json_file(output_path, payload)
    return payload


@dataclass(frozen=True)
class SnapshotResult:
    snapshot_dir: Path
    manifest_path: Path
    file_count: int


def iter_snapshot_sources(memory_dir: Path, include_paths: Iterable[Path]) -> list[Path]:
    sources = list(list_daily_files(memory_dir))
    for extra in include_paths:
        if extra.exists() and extra.is_file():
            sources.append(extra)
    out: list[Path] = []
    seen: set[Path] = set()
    for src in sources:
        resolved = src.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(src)
    return out


def create_memory_snapshot(
    memory_dir: Path,
    snapshot_root: Path,
    *,
    label: str = "",
    include_paths: Iterable[Path] = (),
) -> SnapshotResult:
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    suffix = f"-{label}" if label else ""
    snapshot_dir = snapshot_root / f"{stamp}{suffix}"
    snapshot_dir.mkdir(parents=True, exist_ok=False)

    copied = []
    for src in iter_snapshot_sources(memory_dir, include_paths):
        dst = snapshot_dir / src.name
        shutil.copy2(src, dst)
        copied.append(
            {
                "source_path": str(src),
                "snapshot_path": str(dst),
                "sha256": compute_sha256(dst),
            }
        )

    manifest = {
        "created_at": utc_now().isoformat().replace("+00:00", "Z"),
        "snapshot_dir": str(snapshot_dir),
        "file_count": len(copied),
        "files": copied,
    }
    manifest_path = snapshot_dir / "manifest.json"
    write_json_file(manifest_path, manifest)
    return SnapshotResult(snapshot_dir=snapshot_dir, manifest_path=manifest_path, file_count=len(copied))


def ensure_weekly_distillation_header(memory_md_path: Path) -> str:
    if not memory_md_path.exists():
        return "# MEMORY.md - Long-Term Context\n\n" + WEEKLY_HEADER + "\n"
    content = memory_md_path.read_text(encoding="utf-8", errors="ignore")
    if WEEKLY_HEADER in content:
        return content
    suffix = "" if content.endswith("\n") else "\n"
    return f"{content}{suffix}\n{WEEKLY_HEADER}\n"


def load_distillation_state(state_path: Path) -> dict:
    raw = read_json_file(state_path, {"schema": 1, "weeks": {}})
    if isinstance(raw, list):
        return {"schema": 1, "weeks": {str(item): {} for item in raw if isinstance(item, str)}}
    if not isinstance(raw, dict):
        return {"schema": 1, "weeks": {}}
    weeks = raw.get("weeks")
    if not isinstance(weeks, dict):
        weeks = {}
    return {"schema": 1, "weeks": weeks}


def render_weekly_distillation_block(week_key: str, today: dt.date, bullets: list[dict], source_files: list[Path]) -> str:
    lines = [
        f"### {week_key} ({today.isoformat()})",
        f"- Coverage: last 7 days ending {today.isoformat()}",
        f"- Source files: {len(source_files)}",
    ]
    if bullets:
        lines.append("- Distilled signals:")
        for entry in rank_memory_entries(bullets, today=today)[:8]:
            lines.append(f"  - {entry['text']}")
    else:
        lines.append("- Distilled signals: (no non-placeholder bullets found)")
    return "\n".join(lines) + "\n"


def distill_weekly_memory(
    memory_dir: Path,
    memory_md_path: Path,
    state_path: Path,
    *,
    today: dt.date | None = None,
) -> dict:
    today = today or dt.date.today()
    week = today.isocalendar()
    week_key = f"{week.year}-W{week.week:02d}"
    state = load_distillation_state(state_path)
    if week_key in state["weeks"]:
        return {"updated": False, "week_key": week_key, "reason": "already_distilled"}

    cutoff = today - dt.timedelta(days=6)
    source_files = [p for p in list_daily_files(memory_dir) if cutoff <= (parse_daily_file_date(p) or today) <= today]
    bullet_map = {}
    for path in source_files:
        for entry in extract_memory_bullets(path):
            key = normalize_fragment_key(entry["text"])
            bullet_map.setdefault(key, entry)

    content = ensure_weekly_distillation_header(memory_md_path)
    if f"### {week_key} (" in content:
        state["weeks"][week_key] = {"distilled_at": utc_now().isoformat().replace("+00:00", "Z")}
        write_json_file(state_path, state)
        return {"updated": False, "week_key": week_key, "reason": "section_exists"}

    block = render_weekly_distillation_block(
        week_key,
        today,
        list(bullet_map.values()),
        source_files,
    )
    suffix = "" if content.endswith("\n") else "\n"
    memory_md_path.write_text(f"{content}{suffix}{block}", encoding="utf-8")

    state["weeks"][week_key] = {
        "distilled_at": utc_now().isoformat().replace("+00:00", "Z"),
        "source_count": len(source_files),
        "bullet_count": len(bullet_map),
    }
    write_json_file(state_path, state)
    return {
        "updated": True,
        "week_key": week_key,
        "source_count": len(source_files),
        "bullet_count": len(bullet_map),
    }


def cleanup_forgotten_memory_files(
    memory_dir: Path,
    archive_root: Path,
    *,
    today: dt.date | None = None,
    retain_days: int = 30,
    archive_prune_days: int = 365,
) -> dict:
    today = today or dt.date.today()
    moved = []
    for path in list_daily_files(memory_dir):
        date_value = parse_daily_file_date(path)
        if date_value is None:
            continue
        age = (today - date_value).days
        if age <= retain_days:
            continue
        year_dir = archive_root / str(date_value.year)
        year_dir.mkdir(parents=True, exist_ok=True)
        target = year_dir / path.name
        if target.exists():
            path.unlink()
            continue
        shutil.move(str(path), str(target))
        moved.append(str(target))

    pruned = []
    cutoff = today - dt.timedelta(days=max(0, archive_prune_days))
    if archive_root.exists():
        for archived in sorted(archive_root.rglob("*.md")):
            stat = archived.stat()
            modified = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).date()
            if modified > cutoff:
                continue
            if stat.st_size > 0:
                continue
            archived.unlink()
            pruned.append(str(archived))

    return {
        "moved_count": len(moved),
        "moved": moved,
        "pruned_count": len(pruned),
        "pruned": pruned,
    }


def run_maintain(
    repo_root: Path,
    today: dt.date,
    *,
    with_normalization: bool = True,
    with_snapshot: bool = False,
    with_consolidation: bool = False,
    with_weekly_distill: bool = False,
    with_cleanup: bool = False,
    normalize_window_days: int = 14,
    retain_days: int = 30,
    archive_prune_days: int = 365,
) -> dict:
    memory_dir = repo_root / "memory"
    daily_file, created = ensure_daily_memory_file(memory_dir, today)
    normalization = None
    if with_normalization:
        normalization = normalize_recent_daily_memory_files(
            memory_dir,
            today=today,
            window_days=max(1, normalize_window_days),
        )
    index_path = repo_root / "workspace" / "state_runtime" / "memory" / "memory_index.json"
    index = build_memory_index(memory_dir, index_path)
    health_path = repo_root / "workspace" / "state_runtime" / "memory" / "memory_health.json"
    health = assess_memory_health(
        memory_dir,
        repo_root / "MEMORY.md",
        health_path,
        today=today,
    )

    snapshot_result = None
    if with_snapshot:
        snapshot_result = create_memory_snapshot(
            memory_dir,
            repo_root / "workspace" / "state_runtime" / "memory" / "snapshots",
            label="pre-maintenance",
            include_paths=[repo_root / "MEMORY.md"],
        )

    consolidation = None
    if with_consolidation:
        consolidation = consolidate_memory_fragments(
            memory_dir,
            repo_root / "workspace" / "state_runtime" / "memory" / "heartbeat_consolidation.json",
            today=today,
        )

    weekly_distill = None
    if with_weekly_distill:
        weekly_distill = distill_weekly_memory(
            memory_dir,
            repo_root / "MEMORY.md",
            repo_root / "workspace" / "state_runtime" / "memory" / "weekly_distill_state.json",
            today=today,
        )

    cleanup = None
    if with_cleanup:
        cleanup = cleanup_forgotten_memory_files(
            memory_dir,
            memory_dir / "archive",
            today=today,
            retain_days=retain_days,
            archive_prune_days=archive_prune_days,
        )

    return {
        "daily_file": str(daily_file),
        "created": created,
        "normalization": normalization,
        "index_path": str(index_path),
        "index_total_files": index["total_files"],
        "health_path": str(health_path),
        "compounding_score": health["compounding_score"],
        "snapshot_dir": str(snapshot_result.snapshot_dir) if snapshot_result else None,
        "consolidation": consolidation,
        "weekly_distill": weekly_distill,
        "cleanup": cleanup,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memory maintenance utilities.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    sub = parser.add_subparsers(dest="cmd", required=True)

    rotate = sub.add_parser("rotate", help="Ensure today's daily memory file exists.")
    rotate.add_argument("--date", type=iso_date, default=dt.date.today())

    index = sub.add_parser("index", help="Build memory index for all daily memory files.")
    index.add_argument("--output", default="")

    doctor = sub.add_parser("doctor", help="Assess memory-system health and recent drift.")
    doctor.add_argument("--date", type=iso_date, default=dt.date.today())
    doctor.add_argument("--recent-days", type=int, default=7)
    doctor.add_argument("--output", default="")

    normalize = sub.add_parser("normalize", help="Normalize recent daily memory files conservatively.")
    normalize.add_argument("--date", type=iso_date, default=dt.date.today())
    normalize.add_argument("--window-days", type=int, default=14)

    snapshot = sub.add_parser("snapshot", help="Create a memory snapshot manifest.")
    snapshot.add_argument("--label", default="")
    snapshot.add_argument("--include-memory-md", action="store_true")

    consolidate = sub.add_parser("consolidate", help="Consolidate fragmented bullets from recent daily memory files.")
    consolidate.add_argument("--date", type=iso_date, default=dt.date.today())
    consolidate.add_argument("--window-days", type=int, default=3)
    consolidate.add_argument("--output", default="")

    distill = sub.add_parser("distill-weekly", help="Distill last week of memory into MEMORY.md once per ISO week.")
    distill.add_argument("--date", type=iso_date, default=dt.date.today())
    distill.add_argument("--state-path", default="")

    cleanup = sub.add_parser("cleanup", help="Archive old daily memory files and prune forgotten archived placeholders.")
    cleanup.add_argument("--date", type=iso_date, default=dt.date.today())
    cleanup.add_argument("--retain-days", type=int, default=30)
    cleanup.add_argument("--archive-prune-days", type=int, default=365)

    maintain = sub.add_parser("maintain", help="Rotate + index + optional consolidation, distill, cleanup, snapshot.")
    maintain.add_argument("--date", type=iso_date, default=dt.date.today())
    maintain.add_argument("--with-normalization", action="store_true")
    maintain.add_argument("--without-normalization", action="store_true")
    maintain.add_argument("--normalize-window-days", type=int, default=14)
    maintain.add_argument("--with-snapshot", action="store_true")
    maintain.add_argument("--with-consolidation", action="store_true")
    maintain.add_argument("--with-weekly-distill", action="store_true")
    maintain.add_argument("--with-cleanup", action="store_true")
    maintain.add_argument("--retain-days", type=int, default=30)
    maintain.add_argument("--archive-prune-days", type=int, default=365)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    memory_dir = repo_root / "memory"

    if args.cmd == "rotate":
        path, created = ensure_daily_memory_file(memory_dir, args.date)
        print(json.dumps({"path": str(path), "created": created}, ensure_ascii=True))
        return 0

    if args.cmd == "index":
        output = (
            Path(args.output).resolve()
            if args.output
            else repo_root / "workspace" / "state_runtime" / "memory" / "memory_index.json"
        )
        payload = build_memory_index(memory_dir, output)
        print(json.dumps({"output": str(output), "total_files": payload["total_files"]}, ensure_ascii=True))
        return 0

    if args.cmd == "doctor":
        output = (
            Path(args.output).resolve()
            if args.output
            else repo_root / "workspace" / "state_runtime" / "memory" / "memory_health.json"
        )
        payload = assess_memory_health(
            memory_dir,
            repo_root / "MEMORY.md",
            output,
            today=args.date,
            recent_days=max(1, args.recent_days),
        )
        print(
            json.dumps(
                {
                    "output": str(output),
                    "compounding_score": payload["compounding_score"],
                    "compounding_ready": payload["compounding_ready"],
                    "missing_recent_dates": payload["missing_recent_dates"],
                },
                ensure_ascii=True,
            )
        )
        return 0

    if args.cmd == "normalize":
        payload = normalize_recent_daily_memory_files(
            memory_dir,
            today=args.date,
            window_days=max(1, args.window_days),
        )
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    if args.cmd == "snapshot":
        include = [repo_root / "MEMORY.md"] if args.include_memory_md else []
        result = create_memory_snapshot(
            memory_dir,
            repo_root / "workspace" / "state_runtime" / "memory" / "snapshots",
            label=args.label,
            include_paths=include,
        )
        print(
            json.dumps(
                {
                    "snapshot_dir": str(result.snapshot_dir),
                    "manifest_path": str(result.manifest_path),
                    "file_count": result.file_count,
                },
                ensure_ascii=True,
            )
        )
        return 0

    if args.cmd == "consolidate":
        output = (
            Path(args.output).resolve()
            if args.output
            else repo_root / "workspace" / "state_runtime" / "memory" / "heartbeat_consolidation.json"
        )
        payload = consolidate_memory_fragments(
            memory_dir,
            output,
            today=args.date,
            window_days=max(1, args.window_days),
        )
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    if args.cmd == "distill-weekly":
        state_path = (
            Path(args.state_path).resolve()
            if args.state_path
            else repo_root / "workspace" / "state_runtime" / "memory" / "weekly_distill_state.json"
        )
        payload = distill_weekly_memory(
            memory_dir,
            repo_root / "MEMORY.md",
            state_path,
            today=args.date,
        )
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    if args.cmd == "cleanup":
        payload = cleanup_forgotten_memory_files(
            memory_dir,
            memory_dir / "archive",
            today=args.date,
            retain_days=max(1, args.retain_days),
            archive_prune_days=max(0, args.archive_prune_days),
        )
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    if args.cmd == "maintain":
        with_normalization = True
        if getattr(args, "without_normalization", False):
            with_normalization = False
        elif getattr(args, "with_normalization", False):
            with_normalization = True
        payload = run_maintain(
            repo_root,
            args.date,
            with_normalization=with_normalization,
            with_snapshot=args.with_snapshot,
            with_consolidation=args.with_consolidation,
            with_weekly_distill=args.with_weekly_distill,
            with_cleanup=args.with_cleanup,
            normalize_window_days=max(1, args.normalize_window_days),
            retain_days=max(1, args.retain_days),
            archive_prune_days=max(0, args.archive_prune_days),
        )
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
