#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
VENV_DIR="${OPENCLAW_KB_MLX_VENV:-$ROOT/workspace/runtime/embeddings/.venv_kb_mlx}"
REQ_FILE="$ROOT/workspace/runtime/embeddings/requirements_kb_mlx.txt"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$REQ_FILE"
"$VENV_DIR/bin/python" -m pip install --no-deps mlx-lm==0.31.1
"$VENV_DIR/bin/python" -m pip install --no-deps mlx-vlm==0.4.0
"$VENV_DIR/bin/python" -m pip install --no-deps mlx-embeddings==0.0.5
"$VENV_DIR/bin/python" - <<'PY'
import importlib.util
import mlx_embeddings

assert importlib.util.find_spec("mlx_embeddings") is not None
print("kb_mlx_venv_ready", mlx_embeddings.__file__)
PY
