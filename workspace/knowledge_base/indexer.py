from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chunking import chunk_markdown
from embeddings.driver_mlx import ACCEL_MODEL_ID, CANONICAL_MODEL_ID, MlxEmbedder
from vector_store_lancedb import (
    MINILM_TABLE,
    MODERNBERT_TABLE,
    LanceVectorStore,
    make_row_id,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    override = os.getenv("OPENCLAW_KB_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[2]


def _default_db_dir(repo_root: Path) -> Path:
    override = os.getenv("OPENCLAW_KB_VECTOR_DB_DIR")
    if override:
        return Path(override).resolve()
    return repo_root / "workspace" / "knowledge_base" / "data" / "vectors.lance"


def _meta_path(repo_root: Path) -> Path:
    override = os.getenv("OPENCLAW_KB_EMBED_META_PATH")
    if override:
        return Path(override).resolve()
    return repo_root / "workspace" / "knowledge_base" / "data" / "embeddings.meta.json"


def _load_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "docs": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "docs": {}}


def _save_meta(path: Path, payload: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _relative_doc_id(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _collect_sources(repo_root: Path) -> list[Path]:
    out: list[Path] = []

    kb_data = repo_root / "workspace" / "knowledge_base" / "data"
    if kb_data.exists():
        out.extend(sorted(p for p in kb_data.rglob("*.md") if p.is_file()))

    memory_root = repo_root / "MEMORY.md"
    if memory_root.exists():
        out.append(memory_root)

    daily_dir = repo_root / "memory"
    if daily_dir.exists():
        out.extend(sorted(p for p in daily_dir.glob("*.md") if p.is_file()))

    open_questions = repo_root / "workspace" / "governance" / "OPEN_QUESTIONS.md"
    if open_questions.exists():
        out.append(open_questions)

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in out:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def run_index(evidence_dir: str | None = None) -> dict[str, Any]:
    started = time.time()
    repo_root = _repo_root()
    db_dir = _default_db_dir(repo_root)
    meta_path = _meta_path(repo_root)
    now_iso = _utc_now_iso()

    store = LanceVectorStore(str(db_dir))
    store.ensure_table(MODERNBERT_TABLE, dim=768)
    store.ensure_table(MINILM_TABLE, dim=384)

    docs = _collect_sources(repo_root)
    meta = _load_meta(meta_path)
    meta_docs = meta.setdefault("docs", {})

    embedders = {
        CANONICAL_MODEL_ID: MlxEmbedder(model_id=CANONICAL_MODEL_ID, normalize=True),
        ACCEL_MODEL_ID: MlxEmbedder(model_id=ACCEL_MODEL_ID, normalize=True),
    }

    indexed_docs = 0
    skipped_docs = 0
    modernbert_chunks = 0
    minilm_chunks = 0

    for path in docs:
        rel = _relative_doc_id(path, repo_root)
        text = _read_text(path)
        content_hash = _hash_text(text)

        old = meta_docs.get(rel, {})
        old_models = old.get("models", {})
        unchanged = (
            old.get("sha256") == content_hash
            and old_models.get(CANONICAL_MODEL_ID, {}).get("status") == "indexed"
            and old_models.get(ACCEL_MODEL_ID, {}).get("status") == "indexed"
        )

        if unchanged:
            skipped_docs += 1
            continue

        indexed_docs += 1
        model_entries: dict[str, Any] = {}

        model_plan = [
            (CANONICAL_MODEL_ID, MODERNBERT_TABLE),
            (ACCEL_MODEL_ID, MINILM_TABLE),
        ]

        for model_id, table_name in model_plan:
            chunks = chunk_markdown(text=text, model_id=model_id)
            store.delete_by_doc(table_name, rel)

            if not chunks:
                model_entries[model_id] = {
                    "status": "indexed",
                    "chunks": 0,
                    "updated_at": now_iso,
                }
                continue

            vectors = embedders[model_id].embed_texts([c["text"] for c in chunks])
            rows = []
            for chunk, vec in zip(chunks, vectors):
                row = {
                    "id": make_row_id(rel, chunk["chunk_id"], model_id),
                    "doc_id": rel,
                    "source": "knowledge_base",
                    "path": rel,
                    "section": chunk.get("section", ""),
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "tokens": int(chunk.get("tokens", 0)),
                    "embedding": [float(x) for x in vec],
                    "model_id": model_id,
                    "updated_at": now_iso,
                }
                rows.append(row)

            store.upsert(table_name, rows)

            model_entries[model_id] = {
                "status": "indexed",
                "chunks": len(rows),
                "updated_at": now_iso,
            }
            if model_id == CANONICAL_MODEL_ID:
                modernbert_chunks += len(rows)
            else:
                minilm_chunks += len(rows)

        meta_docs[rel] = {
            "path": rel,
            "sha256": content_hash,
            "last_indexed_at": now_iso,
            "models": model_entries,
        }

    meta["last_run_at"] = now_iso
    _save_meta(meta_path, meta)

    elapsed_s = round(time.time() - started, 3)
    summary = {
        "repo_root": str(repo_root),
        "db_dir": str(db_dir),
        "meta_path": str(meta_path),
        "docs_total": len(docs),
        "docs_indexed": indexed_docs,
        "docs_skipped": skipped_docs,
        "modernbert_chunks": modernbert_chunks,
        "minilm_chunks": minilm_chunks,
        "elapsed_s": elapsed_s,
        "modernbert_stats": store.stats(MODERNBERT_TABLE),
        "minilm_stats": store.stats(MINILM_TABLE),
    }

    print(
        "Indexed docs={docs_indexed}/{docs_total} skipped={docs_skipped} "
        "modernbert_chunks={modernbert_chunks} minilm_chunks={minilm_chunks} "
        "elapsed_s={elapsed_s}".format(**summary)
    )

    report_root = evidence_dir or os.getenv("OPENCLAW_KB_EVIDENCE_DIR")
    if report_root:
        report_dir = Path(report_root)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_name = f"index_report_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        report_path = report_dir / report_name
        report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        summary["report_path"] = str(report_path)
        print(f"Index report: {report_path}")

    return summary
