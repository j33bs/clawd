#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

state_file="$tmp_dir/runtime_autoupdate_state"
log_file="$tmp_dir/runtime_autoupdate.log"

current_sha="$(git rev-parse HEAD)"
current_branch="$(git rev-parse --abbrev-ref HEAD)"
old_sha="$(git rev-parse HEAD~1 2>/dev/null || git rev-parse HEAD)"

{
  printf 'sha=%s\n' "$old_sha"
  printf 'updated_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$state_file"

OPENCLAW_AUTOUPDATE_DRYRUN=1 \
OPENCLAW_AUTOUPDATE_STATE="$state_file" \
OPENCLAW_AUTOUPDATE_LOG="$log_file" \
OPENCLAW_AUTOUPDATE_BRANCH="$current_branch" \
bash "$repo_root/workspace/scripts/openclaw_autoupdate.sh"

grep -q "dry_run=1" "$log_file"
grep -q "new_sha=${current_sha}" "$log_file"
grep -q "target_branch=${current_branch}" "$log_file"

echo "ok: runtime autoupdate dry-run verified"
