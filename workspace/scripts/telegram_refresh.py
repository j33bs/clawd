#!/usr/bin/env python3
"""Refresh Telegram normalized history and vector store from the latest local export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from telegram_ingest import DEFAULT_OUTPUT as DEFAULT_NORMALIZED, ingest_exports
from telegram_vector_store import DEFAULT_STORE_DIR, build_store


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORT_ROOT = REPO_ROOT / "workspace" / "state_runtime" / "ingest" / "telegram_exports"
DEFAULT_EXPORT_SEARCH_ROOTS = (
    Path.home() / "Downloads",
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Library" / "Containers",
    Path.home() / "Library" / "Group Containers",
    Path.home() / "Library" / "Application Support",
)
EXPORT_FILENAMES = ("result.json", "export_results.json")


def _json_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() == ".json" else []
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def _export_json_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.name in EXPORT_FILENAMES else []
    out: list[Path] = []
    for filename in EXPORT_FILENAMES:
        out.extend(path for path in root.rglob(filename) if path.is_file())
    return sorted(set(out))


def _has_git_ancestor(path: Path, stop_at: Path | None = None) -> bool:
    stop = stop_at.resolve() if stop_at else None
    current = path.parent.resolve()
    while True:
        if (current / ".git").exists():
            return True
        if stop and current == stop:
            return False
        if current.parent == current:
            return False
        current = current.parent


def _looks_like_telegram_export(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    chats = payload.get("chats")
    if not isinstance(chats, dict):
        return False
    return isinstance(chats.get("list"), list)


def _candidate_export_dirs(root: Path, *, allow_repo_paths: bool) -> list[Path]:
    grouped: dict[Path, float] = {}
    for path in _export_json_files(root):
        if not allow_repo_paths and _has_git_ancestor(path, stop_at=root):
            continue
        if not _looks_like_telegram_export(path):
            continue
        parent = path.parent
        grouped[parent] = max(grouped.get(parent, 0.0), path.stat().st_mtime)
    return [path for path, _ in sorted(grouped.items(), key=lambda item: (item[1], str(item[0])), reverse=True)]


def _latest_candidate_dirs(root: Path) -> Iterable[Path]:
    grouped: dict[Path, float] = {}
    for path in _json_files(root):
        parent = path.parent
        grouped[parent] = max(grouped.get(parent, 0.0), path.stat().st_mtime)
    return [path for path, _ in sorted(grouped.items(), key=lambda item: (item[1], str(item[0])), reverse=True)]


def discover_latest_export_path(root: Path, *, search_roots: Iterable[Path] | None = None) -> Path | None:
    root = Path(root).expanduser().resolve()
    if root.is_file():
        return root if root.suffix.lower() == ".json" and _looks_like_telegram_export(root) else None
    for candidate in _candidate_export_dirs(root, allow_repo_paths=True):
        return candidate
    for search_root in search_roots or DEFAULT_EXPORT_SEARCH_ROOTS:
        search_root = Path(search_root).expanduser().resolve()
        if search_root == root or not search_root.exists():
            continue
        for candidate in _candidate_export_dirs(search_root, allow_repo_paths=False):
            return candidate
    return None


def refresh_telegram_memory(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    normalized_path: Path = DEFAULT_NORMALIZED,
    store_dir: Path = DEFAULT_STORE_DIR,
    embedder_name: str = "auto",
    backend: str = "auto",
    search_roots: Iterable[Path] | None = None,
) -> dict[str, object]:
    export_root = Path(export_root).expanduser().resolve()
    normalized_path = Path(normalized_path).expanduser().resolve()
    store_dir = Path(store_dir).expanduser().resolve()
    resolved_search_roots = [str(Path(entry).expanduser().resolve()) for entry in (search_roots or DEFAULT_EXPORT_SEARCH_ROOTS)]
    selected_input = discover_latest_export_path(export_root, search_roots=search_roots)

    if selected_input is None:
        if normalized_path.exists():
            build_summary = build_store(
                normalized_path=normalized_path,
                store_dir=store_dir,
                embedder_name=embedder_name,
                force_backend=backend,
            )
            return {
                "status": "rebuilt_from_existing_normalized",
                "selected_input_path": None,
                "normalized_path": str(normalized_path),
                "store_dir": str(store_dir),
                "search_roots": resolved_search_roots,
                "ingest": None,
                "build": build_summary,
            }
        return {
            "status": "skipped",
            "reason": "no_exports_or_normalized_history",
            "selected_input_path": None,
            "normalized_path": str(normalized_path),
            "store_dir": str(store_dir),
            "search_roots": resolved_search_roots,
            "ingest": None,
            "build": None,
        }

    ingest_summary = ingest_exports(selected_input, normalized_path)
    build_summary = build_store(
        normalized_path=normalized_path,
        store_dir=store_dir,
        embedder_name=embedder_name,
        force_backend=backend,
    )
    return {
        "status": "ok",
        "selected_input_path": str(selected_input),
        "normalized_path": str(normalized_path),
        "store_dir": str(store_dir),
        "search_roots": resolved_search_roots,
        "ingest": ingest_summary,
        "build": build_summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh Telegram normalized history and vector store.")
    parser.add_argument("--input-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--normalized", default=str(DEFAULT_NORMALIZED))
    parser.add_argument("--store-dir", default=str(DEFAULT_STORE_DIR))
    parser.add_argument("--embedder", default="auto")
    parser.add_argument("--backend", default="auto", help="auto|lancedb|jsonl")
    parser.add_argument("--search-root", action="append", dest="search_roots")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = refresh_telegram_memory(
        export_root=Path(args.input_root),
        normalized_path=Path(args.normalized),
        store_dir=Path(args.store_dir),
        embedder_name=args.embedder,
        backend=args.backend,
        search_roots=[Path(entry) for entry in args.search_roots] if args.search_roots else None,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    else:
        print(f"status={summary['status']}")
        print(f"selected_input_path={summary.get('selected_input_path')}")
        print(f"normalized_path={summary['normalized_path']}")
        print(f"store_dir={summary['store_dir']}")
        ingest = summary.get("ingest")
        if isinstance(ingest, dict):
            print(f"files_scanned={ingest.get('files_scanned', 0)}")
            print(f"inserted_rows={ingest.get('inserted_rows', 0)}")
            print(f"total_rows={ingest.get('total_rows', 0)}")
        build = summary.get("build")
        if isinstance(build, dict):
            print(f"backend={build.get('backend')}")
            print(f"count={build.get('count', 0)}")
            warning = build.get("warning")
            if warning:
                print(f"warning={warning}")
        reason = summary.get("reason")
        if reason:
            print(f"reason={reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
