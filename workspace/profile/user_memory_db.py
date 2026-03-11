#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
import re


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*-\s+(.+?)\s*$")
FIELD_RE = re.compile(r"^\*\*(.+?)\*\*:\s*(.+)$")


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_db_path(repo_root: Path) -> Path:
    return repo_root / "workspace" / "profile" / "user_memory.db"


def default_export_path(repo_root: Path) -> Path:
    return repo_root / "workspace" / "profile" / "user_memory.jsonl"


def default_dali_inbox_path() -> Path:
    return Path.home() / "inbox.jsonl"


def default_dali_outbox_path() -> Path:
    return Path.home() / "outbox.jsonl"


def default_telegram_path(repo_root: Path) -> Path:
    return repo_root / "workspace" / "state_runtime" / "ingest" / "telegram_normalized" / "messages.jsonl"


def iso_ts_for_path(path: Path) -> str | None:
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", path.stem):
            return f"{path.stem}T00:00:00Z"
        ts = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
        return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except OSError:
        return None


def parse_iso_ts(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def path_label(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.expanduser().resolve())


def normalize_contributor(value: str | None, fallback: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_:@.-]+", "_", text).strip("_")
    return text or fallback


def contributor_for_path(repo_root: Path, path: Path) -> str:
    rel = Path(path_label(repo_root, path))
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "nodes" and parts[2] == "MEMORY.md":
        return parts[1]
    return "c_lawd"


def source_kind_for_path(repo_root: Path, path: Path) -> str:
    rel = Path(path_label(repo_root, path))
    if rel == Path("USER.md"):
        return "user_profile"
    if rel == Path("MEMORY.md"):
        return "long_term_memory"
    if rel.parts[:1] == ("memory",):
        return "daily_memory"
    if len(rel.parts) >= 3 and rel.parts[0] == "nodes" and rel.parts[2] == "MEMORY.md":
        return "node_memory"
    return "memory_note"


def category_for_entry(source_kind: str, section_path: str, text: str) -> str:
    hay = f"{source_kind} {section_path} {text}".lower()
    if "project" in hay:
        return "project"
    if any(token in hay for token in ("preference", "what to call", "timezone", "pronouns", "research:", "briefing:", "daily close:", "autonomy:", "prefers ")):
        return "preference"
    if any(token in hay for token in ("conversation", "check-in", "check in", "heartbeat", "messenger", "correspondence")):
        return "conversation"
    if any(token in hay for token in ("decision", "context", "status", "notes")):
        return "context"
    return "memory"


def title_for_entry(section_path: str, text: str) -> str:
    match = FIELD_RE.match(text)
    if match:
        return match.group(1).strip()
    if section_path:
        return section_path.split(" / ")[-1][:120]
    return text[:120]


def refs_for_entry(rel_path: str, category: str, contributor: str, source_kind: str) -> list[str]:
    return [
        f"path:{rel_path}",
        f"category:{category}",
        f"contributor:{contributor}",
        f"source_kind:{source_kind}",
    ]


def iter_markdown_sources(repo_root: Path) -> list[Path]:
    sources = [
        repo_root / "USER.md",
        repo_root / "MEMORY.md",
        repo_root / "nodes" / "dali" / "MEMORY.md",
        repo_root / "nodes" / "c_lawd" / "MEMORY.md",
    ]
    daily_dir = repo_root / "memory"
    if daily_dir.is_dir():
        sources.extend(sorted(p for p in daily_dir.glob("*.md") if re.match(r"^\d{4}-\d{2}-\d{2}$", p.stem)))
    return [path for path in sources if path.is_file()]


def parse_markdown_entries(repo_root: Path, path: Path) -> list[dict]:
    rel_path = path_label(repo_root, path)
    contributor = contributor_for_path(repo_root, path)
    source_kind = source_kind_for_path(repo_root, path)
    ts = iso_ts_for_path(path)
    headings: list[str] = []
    rows: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        stripped = raw.strip()
        heading = HEADING_RE.match(stripped)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            headings = headings[: max(0, level - 1)]
            headings.append(title)
            continue
        bullet = BULLET_RE.match(raw)
        if not bullet:
            continue
        text = bullet.group(1).strip()
        if not text:
            continue
        section_path = " / ".join(headings)
        category = category_for_entry(source_kind, section_path, text)
        title = title_for_entry(section_path, text)
        refs = refs_for_entry(rel_path, category, contributor, source_kind)
        entry_id = hashlib.sha256(f"{rel_path}:{line_no}:{text}".encode("utf-8")).hexdigest()
        rows.append(
            {
                "id": entry_id,
                "ts": ts,
                "contributor": contributor,
                "source_path": rel_path,
                "source_kind": source_kind,
                "category": category,
                "section_path": section_path,
                "title": title,
                "text": text,
                "refs": refs,
                "line_no": line_no,
            }
        )
    return rows


def parse_dali_messenger_entries(repo_root: Path, path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rel_path = path_label(repo_root, path)
    rows: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = str(payload.get("text") or "").strip()
        if not text:
            continue
        contributor = normalize_contributor(payload.get("from"), "dali")
        ts = parse_iso_ts(payload.get("sent_at")) or parse_iso_ts(payload.get("received_at")) or iso_ts_for_path(path)
        direction = "inbox" if path.name == "inbox.jsonl" else "outbox"
        refs = [
            f"path:{rel_path}",
            "category:conversation",
            f"contributor:{contributor}",
            "source_kind:dali_messenger",
            f"direction:{direction}",
        ]
        entry_id = hashlib.sha256(f"{rel_path}:{line_no}:{text}".encode("utf-8")).hexdigest()
        rows.append(
            {
                "id": entry_id,
                "ts": ts,
                "contributor": contributor,
                "source_path": rel_path,
                "source_kind": "dali_messenger",
                "category": "conversation",
                "section_path": f"dali_messenger / {direction}",
                "title": f"Dali Messenger ({direction})",
                "text": text,
                "refs": refs,
                "line_no": line_no,
            }
        )
    return rows


def parse_telegram_entries(repo_root: Path, path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rel_path = path_label(repo_root, path)
    rows: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = str(payload.get("text") or "").strip()
        if not text:
            continue
        sender_name = payload.get("sender_name") or payload.get("sender_id") or "telegram"
        contributor = normalize_contributor(str(sender_name), "telegram")
        chat_title = str(payload.get("chat_title") or payload.get("chat_id") or "telegram")
        ts = parse_iso_ts(payload.get("timestamp")) or iso_ts_for_path(path)
        refs = [
            f"path:{rel_path}",
            "category:conversation",
            f"contributor:{contributor}",
            "source_kind:telegram_normalized",
            f"chat:{payload.get('chat_id') or chat_title}",
        ]
        entry_id = hashlib.sha256(f"{rel_path}:{line_no}:{text}".encode("utf-8")).hexdigest()
        rows.append(
            {
                "id": entry_id,
                "ts": ts,
                "contributor": contributor,
                "source_path": rel_path,
                "source_kind": "telegram_normalized",
                "category": "conversation",
                "section_path": f"telegram / {chat_title}",
                "title": chat_title[:120],
                "text": text,
                "refs": refs,
                "line_no": line_no,
            }
        )
    return rows


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS user_memory_entries (
            id TEXT PRIMARY KEY,
            ts TEXT,
            contributor TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            category TEXT NOT NULL,
            section_path TEXT NOT NULL,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            refs_json TEXT NOT NULL,
            line_no INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_user_memory_ts ON user_memory_entries(ts);
        CREATE INDEX IF NOT EXISTS idx_user_memory_category ON user_memory_entries(category);
        CREATE INDEX IF NOT EXISTS idx_user_memory_contributor ON user_memory_entries(contributor);
        """
    )


def sync_user_memory(
    repo_root: Path,
    db_path: Path,
    export_path: Path,
    *,
    dali_inbox_path: Path | None = None,
    dali_outbox_path: Path | None = None,
    telegram_path: Path | None = None,
) -> dict:
    repo_root = repo_root.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    source_paths = iter_markdown_sources(repo_root)
    for source_path in source_paths:
        all_rows.extend(parse_markdown_entries(repo_root, source_path))
    extra_sources = [
        ("dali_messenger", Path(dali_inbox_path or default_dali_inbox_path()).expanduser()),
        ("dali_messenger", Path(dali_outbox_path or default_dali_outbox_path()).expanduser()),
        ("telegram_normalized", Path(telegram_path or default_telegram_path(repo_root)).expanduser()),
    ]
    extra_source_paths: list[Path] = []
    for source_type, source_path in extra_sources:
        if not source_path.is_file():
            continue
        extra_source_paths.append(source_path)
        if source_type == "dali_messenger":
            all_rows.extend(parse_dali_messenger_entries(repo_root, source_path))
        else:
            all_rows.extend(parse_telegram_entries(repo_root, source_path))

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_schema(conn)
        with conn:
            conn.execute("DELETE FROM user_memory_entries")
            conn.executemany(
                """
                INSERT INTO user_memory_entries (
                    id, ts, contributor, source_path, source_kind, category,
                    section_path, title, text, refs_json, line_no
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["id"],
                        row["ts"],
                        row["contributor"],
                        row["source_path"],
                        row["source_kind"],
                        row["category"],
                        row["section_path"],
                        row["title"],
                        row["text"],
                        json.dumps(row["refs"], ensure_ascii=True),
                        row["line_no"],
                    )
                    for row in all_rows
                ],
            )
    finally:
        conn.close()

    with export_path.open("w", encoding="utf-8") as handle:
        for row in all_rows:
            item = {
                "source": "user_profile",
                "ts": row["ts"],
                "kind": row["category"],
                "title": row["title"],
                "text": row["text"],
                "refs": row["refs"],
            }
            handle.write(json.dumps(item, ensure_ascii=True) + "\n")

    by_category: dict[str, int] = {}
    by_contributor: dict[str, int] = {}
    for row in all_rows:
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1
        by_contributor[row["contributor"]] = by_contributor.get(row["contributor"], 0) + 1
    return {
        "status": "ok",
        "db_path": str(db_path),
        "export_path": str(export_path),
        "source_count": len(source_paths) + len(extra_source_paths),
        "entry_count": len(all_rows),
        "by_category": by_category,
        "by_contributor": by_contributor,
        "updated_at": utc_now_iso(),
    }


def query_user_memory(db_path: Path, *, q: str = "", category: str = "", contributor: str = "", limit: int = 10) -> list[dict]:
    db_path = db_path.resolve()
    if not db_path.is_file():
        return []
    clauses = []
    params: list[object] = []
    if q.strip():
        clauses.append("LOWER(title || '\n' || text) LIKE ?")
        params.append(f"%{q.strip().lower()}%")
    if category.strip():
        clauses.append("category = ?")
        params.append(category.strip())
    if contributor.strip():
        clauses.append("contributor = ?")
        params.append(contributor.strip())
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT ts, contributor, source_path, source_kind, category, section_path, title, text, refs_json, line_no
        FROM user_memory_entries
        {where_sql}
        ORDER BY COALESCE(ts, '') DESC, source_path ASC, line_no ASC
        LIMIT ?
    """
    params.append(max(1, int(limit)))
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        {
            "ts": row[0],
            "contributor": row[1],
            "source_path": row[2],
            "source_kind": row[3],
            "category": row[4],
            "section_path": row[5],
            "title": row[6],
            "text": row[7],
            "refs": json.loads(row[8]),
            "line_no": row[9],
        }
        for row in rows
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/query the user memory database.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--db-path")
    parser.add_argument("--export-path")
    sub = parser.add_subparsers(dest="command", required=True)
    parser.add_argument("--dali-inbox-path")
    parser.add_argument("--dali-outbox-path")
    parser.add_argument("--telegram-path")

    sub.add_parser("sync", help="Rebuild the user memory DB and JSONL export")

    query_cmd = sub.add_parser("query", help="Query the user memory DB")
    query_cmd.add_argument("--q", default="")
    query_cmd.add_argument("--category", default="")
    query_cmd.add_argument("--contributor", default="")
    query_cmd.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    db_path = Path(args.db_path).resolve() if args.db_path else default_db_path(repo_root)
    export_path = Path(args.export_path).resolve() if args.export_path else default_export_path(repo_root)
    dali_inbox_path = Path(args.dali_inbox_path).expanduser() if args.dali_inbox_path else default_dali_inbox_path()
    dali_outbox_path = Path(args.dali_outbox_path).expanduser() if args.dali_outbox_path else default_dali_outbox_path()
    telegram_path = Path(args.telegram_path).expanduser() if args.telegram_path else default_telegram_path(repo_root)

    if args.command == "sync":
        print(
            json.dumps(
                sync_user_memory(
                    repo_root,
                    db_path,
                    export_path,
                    dali_inbox_path=dali_inbox_path,
                    dali_outbox_path=dali_outbox_path,
                    telegram_path=telegram_path,
                ),
                ensure_ascii=True,
            )
        )
        return 0

    rows = query_user_memory(
        db_path,
        q=getattr(args, "q", ""),
        category=getattr(args, "category", ""),
        contributor=getattr(args, "contributor", ""),
        limit=getattr(args, "limit", 10),
    )
    print(json.dumps({"status": "ok", "rows": rows}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
