#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

pass() { printf "[OK]   %s\n" "$1"; }
fail() { printf "[FAIL] %s\n" "$1"; }

run_step() {
  local name="$1"
  shift
  if "$@"; then
    pass "$name"
  else
    fail "$name"
    return 1
  fi
}

run_step "unit:test_tacti_cr_novel_10" python3 -m unittest tests_unittest.test_tacti_cr_novel_10
run_step "unit:test_policy_router_tacti_novel10" python3 -m unittest tests_unittest.test_policy_router_tacti_novel10
run_step "verify:dream_consolidation" bash workspace/scripts/verify_dream_consolidation.sh
run_step "verify:team_chat_offline" bash workspace/scripts/verify_team_chat.sh
run_step "compile:tacti_modules" python3 -m py_compile \
  workspace/tacti_cr/config.py \
  workspace/tacti_cr/arousal_oscillator.py \
  workspace/tacti_cr/dream_consolidation.py \
  workspace/tacti_cr/semantic_immune.py \
  workspace/tacti_cr/expression.py \
  workspace/tacti_cr/prefetch.py \
  workspace/tacti_cr/mirror.py \
  workspace/tacti_cr/valence.py \
  workspace/tacti_cr/temporal_watchdog.py \
  workspace/hivemind/hivemind/stigmergy.py \
  workspace/source-ui/api/trails.py

echo "All TACTI(C)-R novel-10 checks passed."
