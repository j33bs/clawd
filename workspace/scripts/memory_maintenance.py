#!/usr/bin/env python3
"""Memory maintenance primitives for daily rotation, indexing, and snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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
    return sorted(
        p for p in memory_dir.glob("*.md") if len(p.stem) == 10 and p.stem.count("-") == 2
    )


def build_memory_index(memory_dir: Path, output_path: Path) -> dict:
    entries = []
    for path in list_daily_files(memory_dir):
        content = path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        heading_count = sum(1 for line in lines if line.lstrip().startswith("#"))
        entries.append(
            {
                "date": path.stem,
                "path": str(path),
                "line_count": len(lines),
                "word_count": len(content.split()),
                "heading_count": heading_count,
                "sha256": compute_sha256(path),
                "mtime": dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        )

    payload = {
        "generated_at": utc_now().isoformat().replace("+00:00", "Z"),
        "memory_dir": str(memory_dir),
        "total_files": len(entries),
        "entries": entries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
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
    # Deduplicate while preserving order
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
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return SnapshotResult(snapshot_dir=snapshot_dir, manifest_path=manifest_path, file_count=len(copied))


def run_maintain(repo_root: Path, today: dt.date, with_snapshot: bool = False) -> dict:
    memory_dir = repo_root / "memory"
    daily_file, created = ensure_daily_memory_file(memory_dir, today)
    index_path = repo_root / "workspace" / "state_runtime" / "memory" / "memory_index.json"
    index = build_memory_index(memory_dir, index_path)
    snapshot_result = None
    if with_snapshot:
        snapshot_result = create_memory_snapshot(
            memory_dir,
            repo_root / "workspace" / "state_runtime" / "memory" / "snapshots",
            label="pre-maintenance",
            include_paths=[repo_root / "MEMORY.md"],
        )

    return {
        "daily_file": str(daily_file),
        "created": created,
        "index_path": str(index_path),
        "index_total_files": index["total_files"],
        "snapshot_dir": str(snapshot_result.snapshot_dir) if snapshot_result else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memory maintenance utilities.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    sub = parser.add_subparsers(dest="cmd", required=True)

    rotate = sub.add_parser("rotate", help="Ensure today's daily memory file exists.")
    rotate.add_argument("--date", type=iso_date, default=dt.date.today())

    index = sub.add_parser("index", help="Build memory index for all daily memory files.")
    index.add_argument("--output", default="")

    snapshot = sub.add_parser("snapshot", help="Create a memory snapshot manifest.")
    snapshot.add_argument("--label", default="")
    snapshot.add_argument("--include-memory-md", action="store_true")

    maintain = sub.add_parser("maintain", help="Rotate + index (+ optional snapshot).")
    maintain.add_argument("--date", type=iso_date, default=dt.date.today())
    maintain.add_argument("--with-snapshot", action="store_true")

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

    if args.cmd == "maintain":
        payload = run_maintain(repo_root, args.date, with_snapshot=args.with_snapshot)
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
