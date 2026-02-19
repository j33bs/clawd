#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMPDIR="/tmp/verify_dream_consolidation"
rm -rf "$TMPDIR"
mkdir -p "$TMPDIR/workspace/memory"

cat > "$TMPDIR/workspace/memory/2026-02-19.md" <<'MD'
# 2026-02-19
[09:10] Validated deterministic routing gate behavior.
[10:20] Fixed flaky parser in watchdog module.
[10:40] Validated deterministic routing gate behavior.
[15:00] Added concise audit runbook for reviewers.
MD

PYTHONPATH="$REPO_ROOT/workspace:$REPO_ROOT/workspace/hivemind" \
TACTI_CR_ENABLE=1 TACTI_CR_DREAM_CONSOLIDATION=1 \
python3 - <<'PY' "$TMPDIR"
import json
import os
import sys
from pathlib import Path
from tacti_cr.dream_consolidation import run_consolidation

root = Path(sys.argv[1])
res = run_consolidation(root, day="2026-02-19")
assert res["ok"], res
report = Path(res["report_path"]).read_text(encoding="utf-8")
assert "# Dream Report 2026-02-19" in report, report
assert report.count("- ") >= 5, report
store_lines = Path(res["store_path"]).read_text(encoding="utf-8").splitlines()
assert len(store_lines) >= 2, store_lines
print("ok")
PY
