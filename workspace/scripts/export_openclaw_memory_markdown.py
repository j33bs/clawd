#!/usr/bin/env python3
"""Export external/profile memory into Markdown so native OpenClaw memory can index it."""

from __future__ import annotations

import argparse
import importlib.util as ilu
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "memory" / "ingest" / "external_conversations.md"
USER_MEMORY_DB_PATH = REPO_ROOT / "workspace" / "profile" / "user_memory_db.py"
DEFAULT_SESSION_DIRS = [
    Path.home() / ".openclaw" / "agents" / "main" / "sessions",
    REPO_ROOT / ".openclaw" / "agents" / "research" / "sessions",
    REPO_ROOT / ".openclaw" / "agents" / "codex" / "sessions",
]

_SPEC = ilu.spec_from_file_location("openclaw_user_memory_db", str(USER_MEMORY_DB_PATH))
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load user memory module from {USER_MEMORY_DB_PATH}")
_USER_MEMORY_DB = ilu.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_USER_MEMORY_DB)
default_db_path = _USER_MEMORY_DB.default_db_path
default_export_path = _USER_MEMORY_DB.default_export_path
sync_user_memory = _USER_MEMORY_DB.sync_user_memory


def _parse_ref_value(refs: Iterable[str], prefix: str) -> str:
    needle = f"{prefix}:"
    for ref in refs:
        if ref.startswith(needle):
            return ref.split(":", 1)[1].strip()
    return ""


def _load_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        payload = json.loads(line)
        refs = payload.get("refs", [])
        source_kind = _parse_ref_value(refs, "source_kind")
        contributor = _parse_ref_value(refs, "contributor")
        rows.append(
            {
                "ts": str(payload.get("ts") or ""),
                "kind": str(payload.get("kind") or ""),
                "title": str(payload.get("title") or ""),
                "text": str(payload.get("text") or "").strip(),
                "refs": refs,
                "source_kind": source_kind,
                "contributor": contributor,
            }
        )
    return rows


def _render_line(row: dict, max_text_chars: int) -> str:
    ts = row["ts"] or "unknown-time"
    contributor = row["contributor"] or "unknown"
    source_kind = row["source_kind"] or "unknown"
    title = row["title"] or source_kind
    text = row["text"].replace("\n", " ").strip()
    if len(text) > max_text_chars:
        text = f"{text[: max_text_chars - 1].rstrip()}..."
    return f"- [{ts}] {contributor} | {source_kind} | {title}: {text}"


def _session_agent_id(session_dir: Path) -> str:
    parts = session_dir.parts
    try:
        idx = parts.index("agents")
    except ValueError:
        return session_dir.parent.name or "unknown-agent"
    if idx + 1 >= len(parts):
        return "unknown-agent"
    return parts[idx + 1]


def _extract_text_parts(content: object) -> str:
    if not isinstance(content, list):
        return ""
    texts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = str(item.get("text") or "").strip()
        if text:
            texts.append(text)
    return "\n".join(texts).strip()


def _strip_openclaw_metadata(text: str) -> str:
    cleaned = re.sub(
        r"^Conversation info \(untrusted metadata\):\n```json\n.*?\n```\n\nSender \(untrusted metadata\):\n```json\n.*?\n```\n\n",
        "",
        text,
        flags=re.S,
    ).strip()
    if cleaned.startswith("[cron:") or cleaned.startswith("System:"):
        return ""
    noise_patterns = (
        "Continue where you left off. The previous model attempt failed or timed out.",
        "Reply with exactly OK.",
    )
    if any(pattern in cleaned for pattern in noise_patterns):
        return ""
    return cleaned


def _load_session_rows(session_dirs: Iterable[Path], max_rows: int) -> list[dict]:
    rows: list[dict] = []
    for session_dir in session_dirs:
        session_dir = Path(session_dir).expanduser().resolve()
        if not session_dir.is_dir():
            continue
        agent_id = _session_agent_id(session_dir)
        files = sorted(
            path
            for path in session_dir.glob("*.jsonl")
            if ".deleted." not in path.name
        )
        for path in files:
            for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") != "message":
                    continue
                message = payload.get("message")
                if not isinstance(message, dict) or message.get("role") != "user":
                    continue
                text = _strip_openclaw_metadata(_extract_text_parts(message.get("content")))
                if not text:
                    continue
                rows.append(
                    {
                        "ts": str(payload.get("timestamp") or ""),
                        "kind": "conversation",
                        "title": f"{agent_id} session",
                        "text": text,
                        "refs": [f"agent:{agent_id}", f"path:{path}"],
                        "source_kind": "openclaw_session_user",
                        "contributor": "user",
                    }
                )
    rows.sort(key=lambda row: (row["ts"], row["title"], row["text"]), reverse=True)
    return rows[: max(1, int(max_rows))]


def export_openclaw_memory_markdown(
    repo_root: Path,
    *,
    output_path: Path,
    conversation_limit: int = 160,
    session_limit: int = 120,
    max_text_chars: int = 280,
    dali_inbox_path: Path | None = None,
    dali_outbox_path: Path | None = None,
    telegram_path: Path | None = None,
    session_dirs: Iterable[Path] | None = None,
) -> dict[str, object]:
    repo_root = repo_root.resolve()
    output_path = output_path.resolve()
    db_path = default_db_path(repo_root)
    export_path = default_export_path(repo_root)

    sync_summary = sync_user_memory(
        repo_root,
        db_path,
        export_path,
        dali_inbox_path=dali_inbox_path,
        dali_outbox_path=dali_outbox_path,
        telegram_path=telegram_path,
    )
    rows = _load_rows(export_path)

    conversation_rows = [
        row
        for row in rows
        if row["source_kind"] in {"telegram_normalized", "dali_messenger"}
        and row["text"]
    ]
    conversation_rows.sort(key=lambda row: (row["ts"], row["source_kind"], row["title"], row["text"]), reverse=True)
    selected = conversation_rows[: max(1, int(conversation_limit))]
    session_rows = _load_session_rows(session_dirs or DEFAULT_SESSION_DIRS, session_limit)

    counts = Counter(row["source_kind"] for row in selected)
    session_counts = Counter(_parse_ref_value(row["refs"], "agent") for row in session_rows)
    lines = [
        "# External Conversation Memory",
        "",
        "This file is generated for OpenClaw native memory indexing.",
        "",
        "## Snapshot",
        f"- Updated at: {sync_summary['updated_at']}",
        f"- Source entries in profile DB export: {sync_summary['entry_count']}",
        f"- Conversation entries exported here: {len(selected)}",
        f"- Cross-agent session entries exported here: {len(session_rows)}",
    ]
    if counts:
        lines.append(f"- Conversation sources: {json.dumps(dict(sorted(counts.items())), ensure_ascii=True)}")
    lines.extend(
        [
            "",
            "## Imported Conversations",
        ]
    )
    if selected:
        lines.extend(_render_line(row, max_text_chars) for row in selected)
    else:
        lines.append("- No external conversation history is available yet.")
    lines.extend(
        [
            "",
            "## Cross-Agent Session Messages",
        ]
    )
    if session_counts:
        lines.append(f"- Session agents: {json.dumps(dict(sorted(session_counts.items())), ensure_ascii=True)}")
    if session_rows:
        lines.extend(_render_line(row, max_text_chars) for row in session_rows)
    else:
        lines.append("- No cross-agent session history is available yet.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "output_path": str(output_path),
        "conversation_entries": len(selected),
        "conversation_sources": dict(sorted(counts.items())),
        "session_entries": len(session_rows),
        "session_agents": dict(sorted(session_counts.items())),
        "user_memory": sync_summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw memory bridge Markdown.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--conversation-limit", type=int, default=160)
    parser.add_argument("--session-limit", type=int, default=120)
    parser.add_argument("--max-text-chars", type=int, default=280)
    parser.add_argument("--dali-inbox-path")
    parser.add_argument("--dali-outbox-path")
    parser.add_argument("--telegram-path")
    parser.add_argument("--session-dir", action="append", dest="session_dirs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = export_openclaw_memory_markdown(
        Path(args.repo_root),
        output_path=Path(args.output),
        conversation_limit=args.conversation_limit,
        session_limit=args.session_limit,
        max_text_chars=args.max_text_chars,
        dali_inbox_path=Path(args.dali_inbox_path).expanduser() if args.dali_inbox_path else None,
        dali_outbox_path=Path(args.dali_outbox_path).expanduser() if args.dali_outbox_path else None,
        telegram_path=Path(args.telegram_path).expanduser() if args.telegram_path else None,
        session_dirs=[Path(entry).expanduser() for entry in args.session_dirs] if args.session_dirs else None,
    )
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
