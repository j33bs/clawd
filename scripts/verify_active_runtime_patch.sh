#!/bin/sh
set -u

run_step() {
  cmd="$1"
  if sh -c "$cmd"; then
    return 0
  fi

  echo "FAIL: active runtime patch verification failed"
  echo "FAILED_COMMAND: $cmd"
  echo "REMEDIATION: rerun marker test first (node tests/verify_active_runtime_patch.test.cjs)"
  echo "REMEDIATION: if marker passes and this is a known upgrade, update notes/governance/active_runtime_loader_hash_allowlist.json with computed sha/date/notes"
  echo "REMEDIATION: if marker fails, do NOT allowlist; investigate patch loss"
  return 1
}

run_step "node tests/verify_active_runtime_patch.test.cjs" || exit 1
run_step "node tests/verify_active_runtime_patch_hash.test.cjs" || exit 1

echo "PASS: active runtime patch verification passed"
exit 0
