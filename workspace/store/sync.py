"""
CorrespondenceStore sync engine.

Responsibilities:
- Embed sections (body only — exec_tags/status_tags NEVER in vector)
- Upsert to LanceDB
- Log collisions (never modify markdown)
- Idempotent: safe to re-run for full rebuild

RULE-STORE-002: exec_tags and status_tags are NEVER included in embedding input.
RULE-STORE-005: collision evidence preserved in collision.log + section_number_filed field.
"""
from __future__ import annotations
import os
import time
import lancedb
import pyarrow as pa
from datetime import datetime
from sentence_transformers import SentenceTransformer
from schema import CorrespondenceSection

# Paths
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOVERNANCE_DIR = os.path.join(WORKSPACE, "governance")
STORE_DIR = os.path.join(WORKSPACE, "store", "lancedb_data")
COLLISION_LOG = os.path.join(GOVERNANCE_DIR, "collision.log")
SECTION_COUNT_FILE = os.path.join(GOVERNANCE_DIR, ".section_count")
OQ_PATH = os.path.join(GOVERNANCE_DIR, "OPEN_QUESTIONS.md")

# Embedding model — MiniLM for PoC (fast, local); nomic-embed-text-v1.5 for Dali production
# Switch by setting EMBED_MODEL env var
DEFAULT_MODEL = os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_VERSION = 1

TABLE_NAME = "correspondence"

# Global model cache — load once, reuse across calls to avoid MPS re-init issues
_MODEL_CACHE: dict[str, SentenceTransformer] = {}


def get_embedding_model(model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
    if model_name not in _MODEL_CACHE:
        print(f"  Loading embedding model: {model_name}")
        device = "mps" if _mps_available() else "cpu"
        print(f"  Device: {device}")
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name, device=device)
    return _MODEL_CACHE[model_name]


def _mps_available() -> bool:
    try:
        import torch
        return torch.backends.mps.is_available()
    except ImportError:
        return False


def embed_sections(
    sections: list[CorrespondenceSection],
    model: SentenceTransformer,
    model_name: str = DEFAULT_MODEL,
) -> list[CorrespondenceSection]:
    """
    Embed the body of each section. NEVER embeds exec_tags or status_tags.
    Returns sections with embedding field populated.
    """
    print(f"  Embedding {len(sections)} sections (body only — no exec_tags in vectors)...")
    bodies = [s.body[:2048] for s in sections]  # truncate for model context window
    t0 = time.time()
    vectors = model.encode(bodies, show_progress_bar=True, batch_size=32)
    elapsed = time.time() - t0
    print(f"  Embedded in {elapsed:.1f}s")

    for section, vec in zip(sections, vectors):
        section.embedding = vec.tolist()
        section.embedding_model_version = model_name
        section.embedding_version = EMBEDDING_VERSION

    return sections


def log_collision(section: CorrespondenceSection) -> None:
    """Append a collision event to collision.log. Never modifies markdown."""
    entry = (
        f"{datetime.now().date()} | "
        f"canonical={section.canonical_section_number} | "
        f"filed={section.section_number_filed} | "
        f"authors={','.join(section.authors)} | "
        f"title={section.title[:60]}\n"
    )
    with open(COLLISION_LOG, 'a', encoding='utf-8') as f:
        f.write(entry)


def build_arrow_schema(embedding_dim: int) -> pa.Schema:
    """Build PyArrow schema for LanceDB table."""
    return pa.schema([
        pa.field("canonical_section_number", pa.int32()),
        pa.field("section_number_filed", pa.string()),
        pa.field("collision", pa.bool_()),
        pa.field("authors", pa.list_(pa.string())),
        pa.field("created_at", pa.string()),
        pa.field("is_external_caller", pa.bool_()),
        pa.field("title", pa.string()),
        pa.field("body", pa.string()),
        pa.field("exec_tags", pa.list_(pa.string())),
        pa.field("status_tags", pa.list_(pa.string())),
        pa.field("embedding", pa.list_(pa.float32(), embedding_dim)),
        pa.field("embedding_model_version", pa.string()),
        pa.field("embedding_version", pa.int32()),
        pa.field("retro_dark_fields", pa.list_(pa.string())),
        pa.field("response_to", pa.list_(pa.string())),
        pa.field("knowledge_refs", pa.list_(pa.string())),
    ])


def sections_to_records(sections: list[CorrespondenceSection]) -> list[dict]:
    """Convert CorrespondenceSection objects to dicts for LanceDB upsert."""
    records = []
    for s in sections:
        records.append({
            "canonical_section_number": s.canonical_section_number,
            "section_number_filed": s.section_number_filed,
            "collision": s.collision,
            "authors": s.authors,
            "created_at": s.created_at,
            "is_external_caller": s.is_external_caller,
            "title": s.title,
            "body": s.body,
            "exec_tags": s.exec_tags,
            "status_tags": s.status_tags,
            "embedding": s.embedding,
            "embedding_model_version": s.embedding_model_version,
            "embedding_version": s.embedding_version,
            "retro_dark_fields": s.retro_dark_fields,
            "response_to": s.response_to or [],
            "knowledge_refs": s.knowledge_refs or [],
        })
    return records


def full_rebuild(sections: list[CorrespondenceSection], model_name: str = DEFAULT_MODEL) -> lancedb.table.Table:
    """
    Full idempotent rebuild of the LanceDB table from a list of sections.
    Drops and recreates the table. Returns the table.
    """
    os.makedirs(STORE_DIR, exist_ok=True)
    db = lancedb.connect(STORE_DIR)

    # Load and embed
    model = get_embedding_model(model_name)
    sections = embed_sections(sections, model, model_name)

    # Log any collisions
    collisions = [s for s in sections if s.collision]
    if collisions:
        print(f"  Logging {len(collisions)} collision(s)...")
        for s in collisions:
            log_collision(s)

    # Build records
    records = sections_to_records(sections)

    # Get embedding dimension
    embedding_dim = len(records[0]["embedding"]) if records else 384

    # Drop existing table if present
    existing = db.table_names()
    if TABLE_NAME in existing:
        db.drop_table(TABLE_NAME)
        print(f"  Dropped existing '{TABLE_NAME}' table for rebuild")

    # Create table
    schema = build_arrow_schema(embedding_dim)
    table = db.create_table(TABLE_NAME, data=records, schema=schema)
    print(f"  Created '{TABLE_NAME}' table with {len(records)} sections")

    # Create vector index for semantic search — only if corpus is large enough
    # IVF_PQ requires >= 256 rows to train. For small corpora, flat scan is instant.
    if len(records) >= 256:
        table.create_index(
            metric="cosine",
            vector_column_name="embedding",
            num_partitions=max(4, len(records) // 50),
            num_sub_vectors=16,
        )
        print(f"  IVF_PQ vector index created")
    else:
        print(f"  Flat scan (corpus={len(records)} < 256 rows; no ANN index needed yet)")

    # Update .section_count
    max_canon = max(s.canonical_section_number for s in sections)
    with open(SECTION_COUNT_FILE, 'w') as f:
        f.write(str(max_canon))
    print(f"  .section_count updated to {max_canon}")

    return table


def get_table() -> lancedb.table.Table:
    """Connect to existing store and return the correspondence table."""
    db = lancedb.connect(STORE_DIR)
    return db.open_table(TABLE_NAME)


# ─── Query Interface ────────────────────────────────────────────────────────

def _normalize_df(df):
    """
    Normalize list-type columns returned from LanceDB as numpy arrays.
    LanceDB's to_pandas() returns pa.list_ columns as numpy.ndarray objects.
    We convert them back to Python lists for consistent downstream handling.
    """
    import numpy as np
    list_cols = ["exec_tags", "status_tags", "retro_dark_fields", "response_to",
                 "knowledge_refs", "authors"]
    for col in list_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: list(x) if isinstance(x, np.ndarray) else (x if isinstance(x, list) else [])
            )
    return df


def linear_tail(n: int = 40, from_section: int | None = None) -> list[dict]:
    """
    RULE-STORE-001: Default for external callers.
    Returns last N sections in temporal order (by canonical_section_number).
    """
    table = get_table()
    df = _normalize_df(table.to_pandas())
    df = df.sort_values("canonical_section_number")

    if from_section is not None:
        df = df[df["canonical_section_number"] >= from_section]

    return df.tail(n).to_dict(orient="records")


def semantic_search(
    query: str,
    k: int = 10,
    filters: dict | None = None,
    model_name: str = DEFAULT_MODEL,
) -> list[dict]:
    """
    Opt-in for resident agents. Factual queries only.
    exec_tags and status_tags are applied as POST-retrieval metadata filters.
    They are NEVER used as query vectors. (RULE-STORE-002)
    """
    table = get_table()

    # Load model and embed query (body content only)
    model = get_embedding_model(model_name)
    query_vec = model.encode([query])[0].tolist()

    # Vector search — returns top candidates
    results = _normalize_df(
        table.search(query_vec, vector_column_name="embedding").limit(k * 3).to_pandas()
    )

    # Apply metadata filters POST-retrieval (never pre-retrieval on vectors)
    if filters:
        if "exec_tags" in filters:
            required_tags = set(filters["exec_tags"])
            results = results[results["exec_tags"].apply(
                lambda tags: bool(required_tags.intersection(set(tags)))
            )]
        if "authors" in filters:
            required_authors = set(a.lower() for a in filters["authors"])
            results = results[results["authors"].apply(
                lambda authors: bool(required_authors.intersection(set(a.lower() for a in authors)))
            )]
        if "status_tags" in filters:
            required_status = set(filters["status_tags"])
            results = results[results["status_tags"].apply(
                lambda tags: bool(required_status.intersection(set(tags)))
            )]
        if "is_external_caller" in filters:
            results = results[results["is_external_caller"] == filters["is_external_caller"]]

    return results.head(k).to_dict(orient="records")
