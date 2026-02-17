#!/bin/bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$REPO_ROOT" ]; then
  echo "FAIL: not inside a git repo"
  exit 1
fi

cd "$REPO_ROOT"

node - <<'NODE'
const { approveBaseline, DEFAULT_BASELINE_RELATIVE_PATH } = require('./core/system2/security/integrity_guard');

const baseline = approveBaseline(process.cwd());
console.log(`ok: wrote ${DEFAULT_BASELINE_RELATIVE_PATH} with ${baseline.files.length} anchors`);
NODE
