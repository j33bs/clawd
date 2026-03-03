#!/usr/bin/env bash
set -euo pipefail

TARGET="workspace/OPEN_QUESTIONS.md"

if [[ "${OPENCLAW_GOV_BYPASS:-0}" == "1" ]]; then
  echo "WARN: OPENCLAW_GOV_BYPASS=1 set; skipping OPEN_QUESTIONS append-only guard" >&2
  exit 0
fi

staged_names=$(git diff --cached --name-only --diff-filter=ACMR || true)
if ! printf '%s\n' "$staged_names" | grep -qx "$TARGET"; then
  exit 0
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
head_file="$tmp_dir/head.txt"
staged_file="$tmp_dir/staged.txt"

if git cat-file -e "HEAD:${TARGET}" >/dev/null 2>&1; then
  git show "HEAD:${TARGET}" > "$head_file"
else
  # New file in repo; no prior content to protect.
  exit 0
fi

git show ":${TARGET}" > "$staged_file"

python3 - "$head_file" "$staged_file" <<'PY'
import pathlib
import sys
head = pathlib.Path(sys.argv[1]).read_bytes()
staged = pathlib.Path(sys.argv[2]).read_bytes()
if not staged.startswith(head):
    print("ERROR: append-only policy violation in workspace/OPEN_QUESTIONS.md", file=sys.stderr)
    print("Only pure append operations are allowed; existing content must remain byte-identical prefix.", file=sys.stderr)
    sys.exit(1)
PY
