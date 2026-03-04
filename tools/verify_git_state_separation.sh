#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "${ROOT}" ]; then
  echo "FAIL: not in a git repository" >&2
  exit 1
fi
cd "${ROOT}"

LANCEDB_RULE="workspace/store/lancedb_data/"
SECTION_RULE="workspace/governance/.section_count"

if ! rg -qx "${LANCEDB_RULE}" .gitignore; then
  echo "FAIL: missing ignore rule ${LANCEDB_RULE}" >&2
  exit 1
fi
if ! rg -qx "${SECTION_RULE}" .gitignore; then
  echo "FAIL: missing ignore rule ${SECTION_RULE}" >&2
  exit 1
fi

if [ -n "$(git ls-files workspace/store/lancedb_data)" ]; then
  echo "FAIL: tracked files remain under workspace/store/lancedb_data" >&2
  git ls-files workspace/store/lancedb_data >&2
  exit 1
fi

if [ -n "$(git ls-files workspace/governance/.section_count)" ]; then
  echo "FAIL: workspace/governance/.section_count is still tracked" >&2
  exit 1
fi

echo "PASS: runtime DB and section counter are untracked and ignored"
