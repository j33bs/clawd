#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: tools/verify_embeddings_stack.sh

Runs:
1) python3 -m unittest tests_unittest/test_embeddings_contract.py
2) python3 workspace/knowledge_base/kb.py index
3) python3 workspace/knowledge_base/kb.py query "..."
4) Prints context count from retrieval layer

If mlx-embeddings is unavailable and OPENCLAW_KB_EMBEDDINGS_BACKEND is unset,
the script sets OPENCLAW_KB_EMBEDDINGS_BACKEND=mock for deterministic local verification.
EOF
  exit 0
fi

if [[ -z "${OPENCLAW_KB_EMBEDDINGS_BACKEND:-}" ]]; then
  if ! python3 - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("mlx_embeddings") else 1)
PY
  then
    export OPENCLAW_KB_EMBEDDINGS_BACKEND=mock
    echo "[verify] mlx_embeddings not found; using OPENCLAW_KB_EMBEDDINGS_BACKEND=mock"
  fi
fi

python3 -m unittest tests_unittest/test_embeddings_contract.py
python3 workspace/knowledge_base/kb.py index
python3 workspace/knowledge_base/kb.py query "What does OPEN_QUESTIONS.md discuss?"

python3 - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "workspace" / "knowledge_base"))
from retrieval import retrieve

payload = retrieve("What does OPEN_QUESTIONS.md discuss?", mode="HYBRID", k=6)
print(f"contexts_count={len(payload.get('contexts', []))} authoritative={payload.get('authoritative')}")
PY
