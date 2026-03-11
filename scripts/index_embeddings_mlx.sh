#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: scripts/index_embeddings_mlx.sh [EVIDENCE_DIR]

Builds the KB embedding indexes using:
- ModernBERT (canonical, authoritative): rag_modernbert
- MiniLM (accelerator only): rag_minilm

Optional:
  EVIDENCE_DIR   Directory for index summary artifacts.

Environment:
  OPENCLAW_KB_MLX_VENV            Override the dedicated KB MLX venv path.
  OPENCLAW_KB_EMBEDDINGS_BACKEND=mock   Use deterministic mock embeddings for offline verification.
EOF
  exit 0
fi

EVIDENCE_DIR="${1:-}"
KB_MLX_VENV="${OPENCLAW_KB_MLX_VENV:-$ROOT/workspace/runtime/embeddings/.venv_kb_mlx}"
INDEX_ARGS=()
if [[ -n "$EVIDENCE_DIR" ]]; then
  INDEX_ARGS+=(--evidence-dir "$EVIDENCE_DIR")
fi

if [[ -z "${OPENCLAW_KB_EMBEDDINGS_BACKEND:-}" ]]; then
  if ! OPENCLAW_KB_MLX_VENV="$KB_MLX_VENV" python3 - <<'PY' >/dev/null 2>&1
import sys
from pathlib import Path
import importlib.util

root = Path(Path.cwd() / "workspace" / "knowledge_base" / "embeddings").resolve()
sys.path.insert(0, str(root.parent.parent.parent))
from workspace.knowledge_base.embeddings.driver_mlx import _mlx_embeddings_available

raise SystemExit(0 if _mlx_embeddings_available() else 1)
PY
  then
    export OPENCLAW_KB_EMBEDDINGS_BACKEND=mock
    echo "[index] mlx_embeddings not found in $KB_MLX_VENV; using OPENCLAW_KB_EMBEDDINGS_BACKEND=mock"
  fi
fi

if (( ${#INDEX_ARGS[@]} > 0 )); then
  OPENCLAW_KB_MLX_VENV="$KB_MLX_VENV" python3 workspace/knowledge_base/kb.py index "${INDEX_ARGS[@]}"
else
  OPENCLAW_KB_MLX_VENV="$KB_MLX_VENV" python3 workspace/knowledge_base/kb.py index
fi

OPENCLAW_KB_MLX_VENV="$KB_MLX_VENV" python3 - <<'PY'
import os
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "workspace" / "knowledge_base"))
from vector_store_lancedb import LanceVectorStore, MODERNBERT_TABLE, MINILM_TABLE

store_dir = os.getenv("OPENCLAW_KB_VECTOR_DB_DIR") or str(root / "workspace" / "knowledge_base" / "data" / "vectors.lance")
store = LanceVectorStore(store_dir)
print("ModernBERT stats:", store.stats(MODERNBERT_TABLE))
print("MiniLM stats:", store.stats(MINILM_TABLE))
PY
