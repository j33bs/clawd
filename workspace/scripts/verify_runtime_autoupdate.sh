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
had_node_modules=0
before_node_modules_count=0

if [[ -d node_modules ]]; then
  had_node_modules=1
  before_node_modules_count="$(find node_modules -maxdepth 2 -type f 2>/dev/null | wc -l | tr -d '[:space:]')"
fi

{
  printf 'sha=%s\n' "$old_sha"
  printf 'updated_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$state_file"

OPENCLAW_AUTOUPDATE_DRYRUN=1 \
OPENCLAW_AUTOUPDATE_STATE="$state_file" \
OPENCLAW_AUTOUPDATE_LOG="$log_file" \
OPENCLAW_AUTOUPDATE_TARGET_BRANCH="$current_branch" \
bash "$repo_root/workspace/scripts/openclaw_autoupdate.sh"

grep -q "dry_run=1" "$log_file"
grep -q "new_sha=${current_sha}" "$log_file"
grep -q "target_branch=${current_branch}" "$log_file"
grep -q "planned:" "$log_file"
grep -q "planned:gen_build_stamp:" "$log_file"
grep -q "planned:verify_build_sha:" "$log_file"
if grep -q "executed:" "$log_file"; then
  echo "error: dry-run executed mutating actions" >&2
  exit 1
fi
if grep -q "executed:deps:npm ci" "$log_file"; then
  echo "error: dry-run executed npm ci" >&2
  exit 1
fi
if grep -q "executed:gateway_install:npm install -g . --prefix" "$log_file"; then
  echo "error: dry-run executed gateway install" >&2
  exit 1
fi

if [[ "$had_node_modules" == "1" ]]; then
  after_node_modules_count="$(find node_modules -maxdepth 2 -type f 2>/dev/null | wc -l | tr -d '[:space:]')"
  if [[ "$before_node_modules_count" != "$after_node_modules_count" ]]; then
    echo "error: node_modules changed during dry-run" >&2
    exit 1
  fi
elif [[ -d node_modules ]]; then
  echo "error: node_modules was created during dry-run" >&2
  exit 1
fi

echo "ok: runtime autoupdate dry-run verified"
