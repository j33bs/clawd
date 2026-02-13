#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$repo_root" ]; then
  echo "ERROR: not inside a git repo." >&2
  exit 2
fi

cd "$repo_root"

date_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
branch="$(git branch --show-current 2>/dev/null || echo "unknown")"
head_short="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"

echo "=== CONTEXT BUNDLE (safe) ==="
echo "date_utc=$date_utc"
echo "branch=$branch"
echo "head=$head_short"
echo ""
echo "git_status_porcelain:"
git status --porcelain || true
echo ""

if [ -f "docs/INDEX.md" ]; then
  echo "docs/INDEX.md (head -n 200):"
  sed -n '1,200p' docs/INDEX.md
  echo ""
else
  echo "docs/INDEX.md: (missing)"
  echo ""
fi

latest_handoff="$(ls -1t docs/HANDOFFS/HANDOFF-*.md 2>/dev/null | head -n 1 || true)"
if [ -n "$latest_handoff" ] && [ -f "$latest_handoff" ]; then
  echo "${latest_handoff} (head -n 220):"
  sed -n '1,220p' "$latest_handoff"
  echo ""
else
  echo "docs/HANDOFFS/HANDOFF-*.md: (none)"
  echo ""
fi

