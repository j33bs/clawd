#!/usr/bin/env bash
set -euo pipefail

tmpl="docs/HANDOFF_TEMPLATE.md"

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$repo_root" ]; then
  echo "ERROR: not inside a git repo." >&2
  exit 2
fi

cd "$repo_root"

if [ ! -f "$tmpl" ]; then
  echo "ERROR: missing template: $tmpl" >&2
  exit 2
fi

ts="$(date -u +%Y%m%d-%H%M%S)"
out_dir="docs/HANDOFFS"
out_file="${out_dir}/HANDOFF-${ts}.md"

branch="$(git branch --show-current 2>/dev/null || echo "unknown")"
head_short="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"
status="$(git status --porcelain 2>/dev/null || true)"
date_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$out_dir"

DATE_UTC="$date_utc" \
BRANCH="$branch" \
HEAD_SHORT="$head_short" \
GIT_STATUS_PORCELAIN="$status" \
OBJECTIVE="(fill)" \
PROGRESS="(fill)" \
CURRENT_STATE="(fill)" \
NEXT_STEPS="(fill)" \
VERIFICATION="(fill)" \
NOTES_RISKS="(fill)" \
perl -0pe '
  s/\{\{DATE_UTC\}\}/$ENV{DATE_UTC}/g;
  s/\{\{BRANCH\}\}/$ENV{BRANCH}/g;
  s/\{\{HEAD_SHORT\}\}/$ENV{HEAD_SHORT}/g;
  s/\{\{GIT_STATUS_PORCELAIN\}\}/$ENV{GIT_STATUS_PORCELAIN}/g;
  s/\{\{OBJECTIVE\}\}/$ENV{OBJECTIVE}/g;
  s/\{\{PROGRESS\}\}/$ENV{PROGRESS}/g;
  s/\{\{CURRENT_STATE\}\}/$ENV{CURRENT_STATE}/g;
  s/\{\{NEXT_STEPS\}\}/$ENV{NEXT_STEPS}/g;
  s/\{\{VERIFICATION\}\}/$ENV{VERIFICATION}/g;
  s/\{\{NOTES_RISKS\}\}/$ENV{NOTES_RISKS}/g;
' "$tmpl" > "$out_file"

echo "$out_file"

