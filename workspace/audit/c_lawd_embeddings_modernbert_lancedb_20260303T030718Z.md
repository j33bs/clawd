# C_LAWD Embeddings Audit

## Architecture
- Canonical (authoritative) embedder: `mlx-community/answerdotai-ModernBERT-base-4bit` (768-dim)
- Accelerator-only embedder: `mlx-community/all-MiniLM-L6-v2-4bit` (384-dim)
- Durable vector store: `workspace/knowledge_base/data/vectors.lance/`
- Tables:
  - `rag_modernbert` (authoritative retrieval index)
  - `rag_minilm` (candidate generation only)

## Modes and Fail-Closed Rules
- `FAST`: queries `rag_minilm` only, returns `authoritative=false`, `synthesis_safe=false`.
- `PRECISE`: queries `rag_modernbert` only, `authoritative=true`.
  - Fail-closed if `rag_modernbert` missing/empty (`RuntimeError`).
- `HYBRID` (default): MiniLM candidate generation + ModernBERT rerank/grounding.
  - Final contexts are always ModernBERT-based and authoritative.
  - Fail-closed if ModernBERT table missing/empty.

## Integration Summary
- Added subsystem:
  - `workspace/knowledge_base/embeddings/driver_mlx.py`
  - `workspace/knowledge_base/vector_store_lancedb.py`
  - `workspace/knowledge_base/chunking.py`
  - `workspace/knowledge_base/indexer.py`
  - `workspace/knowledge_base/retrieval.py`
- Integrated seam:
  - `workspace/knowledge_base/agentic/retrieve.py` now routes retrieval through the new subsystem.
  - Graph overlay preserved; retrieved doc IDs/paths are passed into graph results metadata.
  - `workspace/knowledge_base/kb.py` adds `index` subcommand and surfaces retrieval mode/authority.

## Reproduction Commands
1. `python3 -m unittest tests_unittest/test_embeddings_contract.py`
2. `scripts/index_embeddings_mlx.sh`
3. `tools/verify_embeddings_stack.sh`

## Evidence Bundle
- `workspace/audit/_evidence/c_lawd_embeddings_modernbert_lancedb_20260303T030718Z/01_git_status_sb.txt`
- `workspace/audit/_evidence/c_lawd_embeddings_modernbert_lancedb_20260303T030718Z/02_python3_V.txt`
- `workspace/audit/_evidence/c_lawd_embeddings_modernbert_lancedb_20260303T030718Z/03_pip_V.txt`
- `workspace/audit/_evidence/c_lawd_embeddings_modernbert_lancedb_20260303T030718Z/10_unittest_embeddings_contract.txt`
- `workspace/audit/_evidence/c_lawd_embeddings_modernbert_lancedb_20260303T030718Z/11_index_embeddings_mlx.txt`
- `workspace/audit/_evidence/c_lawd_embeddings_modernbert_lancedb_20260303T030718Z/12_verify_embeddings_stack.txt`
- `workspace/audit/_evidence/c_lawd_embeddings_modernbert_lancedb_20260303T030718Z/13_git_status_post_verify.txt`
- `workspace/audit/_evidence/c_lawd_embeddings_modernbert_lancedb_20260303T030718Z/14_kb_index_with_evidence_dir.txt`
- `workspace/audit/_evidence/c_lawd_embeddings_modernbert_lancedb_20260303T030718Z/15_index_reports_list.txt`
- `workspace/audit/_evidence/c_lawd_embeddings_modernbert_lancedb_20260303T030718Z/index_report_20260303T082516Z.json`

## Key Verification Results
- Unit contract test: `Ran 4 tests ... OK`.
- Index script output shows both tables present with expected dims:
  - `rag_modernbert`: 327 rows, 768-dim
  - `rag_minilm`: 439 rows, 384-dim
- Query flow output from `kb.py query`:
  - `Retrieval mode=HYBRID authoritative=True contexts=12`

## LanceDB Rationale (vs SQLite-VSS)
- Native durable local vector storage with explicit table separation for canonical vs accelerator indexes.
- Metadata-rich retrieval (`doc_id`, `path`, `section`, `model_id`) and vector search in one system.
- Better path for multi-index local retrieval than mixing vector concerns into SQLite tables.
