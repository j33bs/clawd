#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DAY="${1:-$(date -u +%Y-%m-%d)}"

PYTHONPATH="$REPO_ROOT/workspace:$REPO_ROOT/workspace/hivemind" \
TACTI_CR_ENABLE=1 TACTI_CR_DREAM_CONSOLIDATION=1 \
python3 - <<'PY' "$REPO_ROOT" "$DAY"
import json
import sys
from pathlib import Path
from tacti_cr.dream_consolidation import run_consolidation

repo = Path(sys.argv[1])
day = sys.argv[2]
result = run_consolidation(repo, day=day)
print(json.dumps(result, ensure_ascii=True))
if not result.get("ok"):
    raise SystemExit(1)
PY
