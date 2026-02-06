#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
WARN=0

log() {
  printf '%s\n' "$*"
}

pass() {
  PASS=$((PASS + 1))
  log "PASS: $*"
}

fail() {
  FAIL=$((FAIL + 1))
  log "FAIL: $*"
}

warn() {
  WARN=$((WARN + 1))
  log "WARN: $*"
}

check_bin() {
  local bin="$1"
  if command -v "$bin" >/dev/null 2>&1; then
    pass "binary available: $bin"
    return 0
  fi
  fail "missing binary: $bin"
  return 1
}

check_env() {
  local key="$1"
  if [[ -n "${!key:-}" ]]; then
    pass "env set: $key"
    return 0
  fi
  fail "missing env: $key"
  return 1
}

check_env_optional() {
  local key="$1"
  if [[ -n "${!key:-}" ]]; then
    pass "env set: $key"
  else
    warn "missing optional env: $key (required for live local-places API calls)"
  fi
}

smoke_cmd() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    pass "smoke: $name"
  else
    fail "smoke: $name"
  fi
}

check_openclaw_skill_ready() {
  local skill="$1"
  local out
  if ! out="$(openclaw skills info "$skill" 2>&1)"; then
    fail "openclaw skills info failed: $skill"
    return
  fi
  if printf '%s' "$out" | grep -Eq '✓ Ready|ready'; then
    pass "openclaw ready: $skill"
  else
    fail "openclaw not ready: $skill"
  fi
}

log "== Dependency checks =="
check_bin peekaboo || true
check_bin summarize || true
check_bin tmux || true
check_bin bird || true
check_bin himalaya || true
check_bin uv || true
check_bin codexbar || true
check_bin whisper || true
check_env_optional GOOGLE_PLACES_API_KEY

log ""
log "== Smoke checks =="
smoke_cmd "peakaboo/peekaboo help" peekaboo --help
smoke_cmd "summarize help" summarize --help
smoke_cmd "tmux version" tmux -V
smoke_cmd "bird help" bird --help
smoke_cmd "himalaya help" himalaya --help
smoke_cmd "uv version" uv --version
smoke_cmd "model_usage adapter help" python3 "$REPO_ROOT/skills/model-usage/scripts/model_usage.py" --help
smoke_cmd "codexbar help" codexbar --help
smoke_cmd "whisper help" whisper --help

log ""
log "== OpenClaw skill readiness =="
check_openclaw_skill_ready peakaboo
check_openclaw_skill_ready summarize
check_openclaw_skill_ready tmux
check_openclaw_skill_ready bird
check_openclaw_skill_ready himalaya
check_openclaw_skill_ready local-places
check_openclaw_skill_ready model-usage
check_openclaw_skill_ready openai-whisper

log ""
log "== Summary =="
log "PASS: $PASS"
log "WARN: $WARN"
log "FAIL: $FAIL"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
