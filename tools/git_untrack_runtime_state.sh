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

lancedb_removed=0
section_removed=0

if [ -n "$(git ls-files workspace/store/lancedb_data)" ]; then
  git rm -r --cached workspace/store/lancedb_data >/dev/null
  lancedb_removed=1
fi

if [ -n "$(git ls-files workspace/governance/.section_count)" ]; then
  git rm --cached workspace/governance/.section_count >/dev/null
  section_removed=1
fi

echo "UNTRACK_RUNTIME_STATE: lancedb_removed=${lancedb_removed} section_count_removed=${section_removed}"
