from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from embeddings.driver_mlx import ACCEL_MODEL_ID, CANONICAL_MODEL_ID, MlxEmbedder
from vector_store_lancedb import (
    MINILM_DIM,
    MINILM_TABLE,
    MODERNBERT_DIM,
    MODERNBERT_TABLE,
    LanceVectorStore,
)


def _repo_root() -> Path:
    override = os.getenv("OPENCLAW_KB_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[2]


def _default_db_dir() -> Path:
    override = os.getenv("OPENCLAW_KB_VECTOR_DB_DIR")
    if override:
        return Path(override).resolve()
    return _repo_root() / "workspace" / "knowledge_base" / "data" / "vectors.lance"


def _doc_filter(doc_ids: list[str]) -> str | None:
    ids = [doc_id.replace("'", "''") for doc_id in doc_ids if doc_id]
    if not ids:
        return None
    joined = ", ".join(f"'{doc_id}'" for doc_id in ids)
    return f"doc_id IN ({joined})"


def _rows_to_contexts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for row in rows:
        contexts.append(
            {
                "text": row.get("text", ""),
                "path": row.get("path", ""),
                "doc_id": row.get("doc_id", ""),
                "chunk_id": row.get("chunk_id", ""),
                "section": row.get("section", ""),
                "model_id": row.get("model_id", ""),
                "score": row.get("score"),
                "distance": row.get("distance"),
            }
        )
    return contexts


def _ensure_modernbert_available(store: LanceVectorStore):
    store.assert_table_dim(MODERNBERT_TABLE, expected_dim=MODERNBERT_DIM, require_exists=False)
    stats = store.stats(MODERNBERT_TABLE)
    if not stats.get("exists"):
        raise RuntimeError("ModernBERT index unavailable: rag_modernbert table is missing")
    if int(stats.get("rows", 0)) <= 0:
        raise RuntimeError(
            "ModernBERT index unavailable: rag_modernbert exists but is empty; run `kb.py index`"
        )


def _assert_known_dims(store: LanceVectorStore):
    store.assert_table_dim(MODERNBERT_TABLE, expected_dim=MODERNBERT_DIM, require_exists=False)
    store.assert_table_dim(MINILM_TABLE, expected_dim=MINILM_DIM, require_exists=False)


def retrieve(query: str, mode: str = "HYBRID", k: int = 12) -> dict:
    selected_mode = str(mode or "HYBRID").upper()
    if selected_mode not in {"FAST", "PRECISE", "HYBRID"}:
        raise ValueError(f"Unsupported retrieval mode: {mode}")

    store = LanceVectorStore(str(_default_db_dir()))
    _assert_known_dims(store)
    k = max(1, int(k))

    if selected_mode == "FAST":
        minilm_stats = store.stats(MINILM_TABLE)
        if not minilm_stats.get("exists") or int(minilm_stats.get("rows", 0)) <= 0:
            contexts: list[dict[str, Any]] = []
            candidates: list[dict[str, Any]] = []
        else:
            qvec = MlxEmbedder(model_id=ACCEL_MODEL_ID, normalize=True).embed_texts([query])[0]
            rows = store.query(MINILM_TABLE, qvec, k=k)
            contexts = _rows_to_contexts(rows)
            candidates = contexts

        return {
            "authoritative": False,
            "synthesis_safe": False,
            "mode": "FAST",
            "contexts": contexts,
            "candidates": candidates,
            "notes": ["FAST mode is candidate-only and must not be used for final synthesis grounding."],
        }

    if selected_mode == "PRECISE":
        _ensure_modernbert_available(store)
        qvec = MlxEmbedder(model_id=CANONICAL_MODEL_ID, normalize=True).embed_texts([query])[0]
        rows = store.query(MODERNBERT_TABLE, qvec, k=k)
        contexts = _rows_to_contexts(rows)
        return {
            "authoritative": True,
            "synthesis_safe": True,
            "mode": "PRECISE",
            "contexts": contexts,
            "candidates": [],
        }

    _ensure_modernbert_available(store)

    minilm_candidates: list[dict[str, Any]] = []
    candidate_doc_ids: list[str] = []
    minilm_stats = store.stats(MINILM_TABLE)
    if minilm_stats.get("exists") and int(minilm_stats.get("rows", 0)) > 0:
        minilm_qvec = MlxEmbedder(model_id=ACCEL_MODEL_ID, normalize=True).embed_texts([query])[0]
        candidate_rows = store.query(MINILM_TABLE, minilm_qvec, k=120)
        minilm_candidates = _rows_to_contexts(candidate_rows)
        seen: set[str] = set()
        for row in minilm_candidates:
            doc_id = str(row.get("doc_id", ""))
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            candidate_doc_ids.append(doc_id)

    modern_qvec = MlxEmbedder(model_id=CANONICAL_MODEL_ID, normalize=True).embed_texts([query])[0]
    where = _doc_filter(candidate_doc_ids)
    rows = store.query(MODERNBERT_TABLE, modern_qvec, k=k, where=where)
    if where and not rows:
        rows = store.query(MODERNBERT_TABLE, modern_qvec, k=k)

    return {
        "authoritative": True,
        "synthesis_safe": True,
        "mode": "HYBRID",
        "contexts": _rows_to_contexts(rows),
        "candidates": minilm_candidates,
    }
