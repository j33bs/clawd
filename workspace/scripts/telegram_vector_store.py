#!/usr/bin/env python3
"""Telegram vector store builder/query with LanceDB-first backend."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from telegram_embed import build_embedder, cosine_similarity


DEFAULT_NORMALIZED = Path("workspace/state_runtime/ingest/telegram_normalized/messages.jsonl")
DEFAULT_STORE_DIR = Path("workspace/state_runtime/vectorstores/telegram/lancedb")
DEFAULT_TABLE = "telegram_messages"
DEFAULT_BATCH_SIZE = 32


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: (str(row.get("timestamp", "")), str(row.get("hash", ""))))
    with path.open("w", encoding="utf-8") as fh:
        for row in ordered:
            fh.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def detect_lancedb_available() -> bool:
    try:
        import lancedb  # noqa: F401
        import pyarrow  # noqa: F401

        return True
    except Exception:
        return False


def records_path(store_dir: Path) -> Path:
    return store_dir / f"{DEFAULT_TABLE}.jsonl"


def metadata_path(store_dir: Path) -> Path:
    return store_dir / "store_meta.json"


def write_metadata(store_dir: Path, payload: dict[str, Any]) -> None:
    path = metadata_path(store_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def read_metadata(store_dir: Path) -> dict[str, Any]:
    path = metadata_path(store_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def to_store_record(row: dict[str, Any], embedding: list[float]) -> dict[str, Any]:
    return {
        "hash": row.get("hash"),
        "chat_id": str(row.get("chat_id")),
        "chat_title": row.get("chat_title"),
        "message_id": str(row.get("message_id")),
        "timestamp": row.get("timestamp"),
        "sender_name": row.get("sender_name"),
        "text": row.get("text"),
        "embedding": [float(x) for x in embedding],
        "reply_to_message_id": row.get("reply_to_message_id"),
    }


def build_json_backend(
    normalized_rows: list[dict[str, Any]],
    *,
    store_dir: Path,
    embedder_name: str,
    batch_size: int,
) -> dict[str, Any]:
    embedder = build_embedder(embedder_name)
    current = {row.get("hash"): row for row in load_jsonl(records_path(store_dir)) if row.get("hash")}
    inserted = 0
    skipped_existing = 0

    pending = [row for row in normalized_rows if row.get("hash")]
    for start in range(0, len(pending), batch_size):
        chunk = pending[start : start + batch_size]
        texts = [str(row.get("text", "")) for row in chunk]
        vectors = embedder.embed(texts)
        for row, vector in zip(chunk, vectors):
            row_hash = str(row["hash"])
            if row_hash in current:
                skipped_existing += 1
                continue
            current[row_hash] = to_store_record(row, vector)
            inserted += 1

    rows_out = [row for row in current.values() if isinstance(row, dict)]
    write_jsonl(records_path(store_dir), rows_out)
    dim = len(rows_out[0]["embedding"]) if rows_out else getattr(embedder, "dim", 0)
    meta = {
        "backend": "jsonl",
        "embedder_name": getattr(embedder, "name", str(embedder_name or "auto")),
        "embedding_dim": dim,
        "count": len(rows_out),
    }
    write_metadata(store_dir, meta)
    return {
        "backend": "jsonl",
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "count": len(rows_out),
        "embedder_name": meta["embedder_name"],
        "embedding_dim": dim,
        "store_dir": str(store_dir),
    }


def _escape_sql(value: str) -> str:
    return value.replace("'", "''")


def build_lancedb_backend(
    normalized_rows: list[dict[str, Any]],
    *,
    store_dir: Path,
    embedder_name: str,
    batch_size: int,
) -> dict[str, Any]:
    import lancedb
    import pyarrow as pa

    embedder = build_embedder(embedder_name)
    store_dir.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(store_dir))

    pending = [row for row in normalized_rows if row.get("hash")]
    records: list[dict[str, Any]] = []
    for start in range(0, len(pending), batch_size):
        chunk = pending[start : start + batch_size]
        texts = [str(row.get("text", "")) for row in chunk]
        vectors = embedder.embed(texts)
        for row, vector in zip(chunk, vectors):
            records.append(to_store_record(row, vector))

    dim = len(records[0]["embedding"]) if records else getattr(embedder, "dim", 0)
    if DEFAULT_TABLE not in db.table_names():
        schema = pa.schema(
            [
                pa.field("hash", pa.string()),
                pa.field("chat_id", pa.string()),
                pa.field("chat_title", pa.string()),
                pa.field("message_id", pa.string()),
                pa.field("timestamp", pa.string()),
                pa.field("sender_name", pa.string()),
                pa.field("text", pa.string()),
                pa.field("embedding", pa.list_(pa.float32(), dim)),
                pa.field("reply_to_message_id", pa.string()),
            ]
        )
        table = db.create_table(DEFAULT_TABLE, data=records, schema=schema)
        inserted = len(records)
        skipped_existing = 0
    else:
        table = db.open_table(DEFAULT_TABLE)
        inserted = 0
        skipped_existing = 0
        for row in records:
            row_hash = str(row["hash"])
            table.delete(f"hash = '{_escape_sql(row_hash)}'")
            table.add([row])
            inserted += 1
        existing_count = len(table.to_arrow())
        skipped_existing = max(0, existing_count - inserted)

    if inserted >= 256:
        try:
            table.create_index(metric="cosine", vector_column_name="embedding")
        except Exception:
            pass

    total_count = len(table.to_arrow())
    meta = {
        "backend": "lancedb",
        "embedder_name": getattr(embedder, "name", str(embedder_name or "auto")),
        "embedding_dim": dim,
        "count": total_count,
    }
    write_metadata(store_dir, meta)
    return {
        "backend": "lancedb",
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "count": total_count,
        "embedder_name": meta["embedder_name"],
        "embedding_dim": dim,
        "store_dir": str(store_dir),
    }


def build_store(
    normalized_path: Path = DEFAULT_NORMALIZED,
    store_dir: Path = DEFAULT_STORE_DIR,
    *,
    embedder_name: str = "auto",
    batch_size: int = DEFAULT_BATCH_SIZE,
    force_backend: str = "auto",
) -> dict[str, Any]:
    rows = load_jsonl(normalized_path)
    deduped = {str(row["hash"]): row for row in rows if isinstance(row, dict) and row.get("hash")}
    normalized_rows = list(deduped.values())

    backend = force_backend.strip().lower()
    if backend not in {"auto", "lancedb", "jsonl"}:
        backend = "auto"
    if backend == "auto":
        backend = "lancedb" if detect_lancedb_available() else "jsonl"

    if backend == "lancedb":
        try:
            return build_lancedb_backend(
                normalized_rows,
                store_dir=store_dir,
                embedder_name=embedder_name,
                batch_size=max(1, int(batch_size)),
            )
        except Exception as exc:
            fallback = build_json_backend(
                normalized_rows,
                store_dir=store_dir,
                embedder_name=embedder_name,
                batch_size=max(1, int(batch_size)),
            )
            fallback["warning"] = f"lancedb_unavailable_fallback={exc}"
            return fallback

    return build_json_backend(
        normalized_rows,
        store_dir=store_dir,
        embedder_name=embedder_name,
        batch_size=max(1, int(batch_size)),
    )


def _apply_filters(
    rows: list[dict[str, Any]],
    *,
    chat_id: str | None = None,
    after: str | None = None,
    before: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        ts = str(row.get("timestamp", ""))
        if chat_id and str(row.get("chat_id")) != str(chat_id):
            continue
        if after and ts < after:
            continue
        if before and ts > before:
            continue
        out.append(row)
    return out


def search_store(
    query: str,
    *,
    topk: int = 8,
    chat_id: str | None = None,
    after: str | None = None,
    before: str | None = None,
    store_dir: Path = DEFAULT_STORE_DIR,
) -> list[dict[str, Any]]:
    meta = read_metadata(store_dir)
    backend = str(meta.get("backend", "jsonl"))
    embedder_name = str(meta.get("embedder_name", "auto"))
    embedder = build_embedder(embedder_name)
    query_vec = embedder.embed([query])[0]

    if backend == "lancedb" and detect_lancedb_available():
        try:
            import lancedb

            db = lancedb.connect(str(store_dir))
            table = db.open_table(DEFAULT_TABLE)
            rows = table.search(query_vec, vector_column_name="embedding").limit(max(1, topk * 5)).to_arrow().to_pylist()
            filtered = _apply_filters(rows, chat_id=chat_id, after=after, before=before)
            for row in filtered:
                row["_score"] = float(row.get("_distance", 0.0))
            # smaller distance is better
            filtered.sort(key=lambda row: float(row.get("_score", 999999.0)))
            return filtered[: max(1, topk)]
        except Exception:
            backend = "jsonl"

    rows = load_jsonl(records_path(store_dir))
    filtered = _apply_filters(rows, chat_id=chat_id, after=after, before=before)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for row in filtered:
        embedding = row.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            continue
        score = cosine_similarity(query_vec, [float(x) for x in embedding])
        ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    out = []
    for score, row in ranked[: max(1, topk)]:
        copy = dict(row)
        copy["_score"] = float(score)
        out.append(copy)
    return out


def store_stats(store_dir: Path = DEFAULT_STORE_DIR) -> dict[str, Any]:
    files = [p for p in store_dir.rglob("*") if p.is_file()] if store_dir.exists() else []
    total_bytes = sum(p.stat().st_size for p in files)
    meta = read_metadata(store_dir)
    count = 0
    if meta.get("backend") == "lancedb" and detect_lancedb_available():
        try:
            import lancedb

            db = lancedb.connect(str(store_dir))
            table = db.open_table(DEFAULT_TABLE)
            count = len(table.to_arrow())
        except Exception:
            count = len(load_jsonl(records_path(store_dir)))
    else:
        count = len(load_jsonl(records_path(store_dir)))
    return {
        "store_dir": str(store_dir),
        "backend": meta.get("backend", "jsonl"),
        "count": count,
        "approx_bytes": total_bytes,
        "embedder_name": meta.get("embedder_name"),
        "embedding_dim": meta.get("embedding_dim"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build/query Telegram vector store.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    build = sub.add_parser("build")
    build.add_argument("--normalized", default=str(DEFAULT_NORMALIZED))
    build.add_argument("--store-dir", default=str(DEFAULT_STORE_DIR))
    build.add_argument("--embedder", default="auto")
    build.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    build.add_argument("--backend", default="auto", help="auto|lancedb|jsonl")

    stats = sub.add_parser("stats")
    stats.add_argument("--store-dir", default=str(DEFAULT_STORE_DIR))

    query = sub.add_parser("query")
    query.add_argument("text")
    query.add_argument("--store-dir", default=str(DEFAULT_STORE_DIR))
    query.add_argument("--topk", type=int, default=8)
    query.add_argument("--chat")
    query.add_argument("--after")
    query.add_argument("--before")
    query.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.cmd == "build":
        summary = build_store(
            Path(args.normalized).resolve(),
            Path(args.store_dir).resolve(),
            embedder_name=args.embedder,
            batch_size=max(1, int(args.batch_size)),
            force_backend=args.backend,
        )
        print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
        return 0

    if args.cmd == "stats":
        summary = store_stats(Path(args.store_dir).resolve())
        print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
        return 0

    if args.cmd == "query":
        rows = search_store(
            args.text,
            topk=max(1, int(args.topk)),
            chat_id=args.chat,
            after=args.after,
            before=args.before,
            store_dir=Path(args.store_dir).resolve(),
        )
        if args.json:
            print(json.dumps(rows, ensure_ascii=True, sort_keys=True))
        else:
            for idx, row in enumerate(rows, start=1):
                snippet = str(row.get("text", ""))[:200].replace("\n", " ")
                print(
                    f"{idx}. score={row.get('_score')} ts={row.get('timestamp')} sender={row.get('sender_name')} "
                    f"chat={row.get('chat_title')} message_id={row.get('message_id')} hash={row.get('hash')} text={snippet}"
                )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
