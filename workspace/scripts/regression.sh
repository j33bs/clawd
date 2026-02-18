#!/bin/bash
# OpenClaw Regression Validation
# Category: B (Security)
# MUST pass before any change admission
#
# Usage: ./workspace/scripts/regression.sh
# Exit: 0 on pass, 1 on failure

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "  OpenClaw Regression Validation"
echo "=========================================="
echo ""

FAILURES=0
WARNINGS=0
REGRESSION_PROFILE="${REGRESSION_PROFILE:-core}"

# Helper function
check_pass() {
    echo -e "${GREEN}  ✓ PASS${NC}"
}

check_fail() {
    echo -e "${RED}  ✗ FAIL: $1${NC}"
    FAILURES=$((FAILURES + 1))
}

check_warn() {
    echo -e "${YELLOW}  ⚠ WARN: $1${NC}"
    WARNINGS=$((WARNINGS + 1))
}

# ============================================
# 1. CONSTITUTIONAL INVARIANTS
# ============================================
echo "[1/9] Checking constitutional invariants..."

if [ -f "workspace/CONSTITUTION.md" ]; then
    if grep -q "Article III: Safety Boundaries" workspace/CONSTITUTION.md; then
        check_pass
    else
        check_fail "CONSTITUTION.md missing safety boundaries section"
    fi
else
    check_fail "CONSTITUTION.md not found"
fi

# ============================================
# 2. GOVERNANCE SUBSTRATE
# ============================================
echo "[2/9] Verifying governance substrate..."

if [ -f "workspace/governance/GOVERNANCE_LOG.md" ]; then
    check_pass
else
    check_fail "Governance log missing"
fi

# ============================================
# 3. SECRET SCAN (tracked files)
# ============================================
echo "[3/9] Scanning for secrets in tracked files..."

# Get list of tracked files
TRACKED_FILES=$(git ls-files 2>/dev/null || echo "")

SECRET_FOUND=0
for file in $TRACKED_FILES; do
    # Skip files that contain patterns (not actual secrets)
    if [[ "$file" == *.md ]] || [[ "$file" == *.template ]] || [[ "$file" == .gitignore ]] || [[ "$file" == *.sh ]]; then
        continue
    fi

    # Check for obvious secret patterns
    if [ -f "$file" ]; then
        if grep -lE "(PRIV[_ ]?KEY|BEGIN.*KEY|sk-ant-|bearers+[a-zA-Z0-9_-]{20,})" "$file" 2>/dev/null; then
            echo "    Found in: $file"
            SECRET_FOUND=1
        fi
    fi
done

if [ $SECRET_FOUND -eq 1 ]; then
    check_fail "Potential secrets in tracked files"
else
    check_pass
fi

# ============================================
# 4. FORBIDDEN FILES CHECK
# ============================================
echo "[4/9] Checking for forbidden files..."

FORBIDDEN_FOUND=0
FORBIDDEN_PATTERNS="secrets.env device.json paired.json auth-profiles.json device-auth.json"

for pattern in $FORBIDDEN_PATTERNS; do
    if echo "$TRACKED_FILES" | grep -qE "(^|/)${pattern}$"; then
        echo "    Forbidden file tracked: $pattern"
        FORBIDDEN_FOUND=1
    fi
done

if [ $FORBIDDEN_FOUND -eq 1 ]; then
    check_fail "Forbidden files tracked in repository"
else
    check_pass
fi

# ============================================
# 5. HOOKS INSTALLED
# ============================================
echo "[5/9] Verifying git hooks..."

HOOKS_OK=1
if [ ! -x ".git/hooks/pre-commit" ]; then
    echo "    pre-commit hook missing or not executable"
    HOOKS_OK=0
fi

if [ ! -x ".git/hooks/pre-push" ]; then
    echo "    pre-push hook missing or not executable"
    HOOKS_OK=0
fi

if [ $HOOKS_OK -eq 1 ]; then
    check_pass
else
    check_warn "Git hooks not installed (run: bash workspace/scripts/install-hooks.sh)"
fi

# ============================================
# 6. DOCUMENTATION COMPLETENESS
# ============================================
echo "[6/9] Checking documentation completeness..."

DOCS_OK=1
REQUIRED_DOCS="CONSTITUTION SOUL IDENTITY AGENTS USER BOUNDARIES"

for doc in $REQUIRED_DOCS; do
    if [ ! -f "workspace/$doc.md" ]; then
        echo "    Missing: $doc.md"
        DOCS_OK=0
    fi
done

if [ $DOCS_OK -eq 1 ]; then
    check_pass
else
    check_fail "Required documentation missing"
fi

# ============================================
# 7. OPTIONAL PROVIDER ENV GATING
# ============================================
echo "[7/9] Checking provider env gating (profile=${REGRESSION_PROFILE})..."

if [ -f "openclaw.json" ]; then
    set +e
    REGRESSION_PROFILE="${REGRESSION_PROFILE}" python3 - <<'PY'
import json
import os
import sys

def has_env(value):
    if isinstance(value, str):
        return "${" in value
    if isinstance(value, dict):
        return any(has_env(v) for v in value.values())
    if isinstance(value, list):
        return any(has_env(v) for v in value)
    return False

with open("openclaw.json", "r", encoding="utf-8") as handle:
    data = json.load(handle)

profile = os.environ.get("REGRESSION_PROFILE", "core").strip().lower()
providers = data.get("models", {}).get("providers", {})

if not isinstance(providers, dict):
    print("providers_invalid")
    sys.exit(2)

if profile == "paid":
    for name in ("anthropic",):
        provider = providers.get(name)
        if not isinstance(provider, dict):
            print(f"missing_paid:{name}")
            sys.exit(3)

for name, provider in providers.items():
    if not isinstance(provider, dict):
        continue
    if has_env(provider):
        enabled = provider.get("enabled")
        if enabled not in ("auto", False):
            print(f"enabled:{name}:{enabled}")
            sys.exit(4)

print("ok")
PY
    PROVIDER_GATE_RC=$?
    set -e
    if [ ${PROVIDER_GATE_RC} -eq 0 ]; then
        check_pass
    else
        check_fail "Provider env gating check failed (profile=${REGRESSION_PROFILE})"
    fi
else
    check_fail "openclaw.json not found for provider gating check"
fi

# ============================================
# 8. HEARTBEAT DEPENDENCY INVARIANT
# ============================================
echo "[8/9] Checking heartbeat dependency invariant..."

if [ -f "workspace/automation/cron_jobs.json" ]; then
    NEEDS_HEARTBEAT=$(python3 - <<'PY'
import json
from pathlib import Path

path = Path("workspace/automation/cron_jobs.json")
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("error")
    raise SystemExit(0)

jobs = data.get("jobs", []) if isinstance(data, dict) else []
if not isinstance(jobs, list):
    print("error")
    raise SystemExit(0)

for job in jobs:
    if not isinstance(job, dict):
        continue
    session_target = str(job.get("sessionTarget", "")).strip()
    wake_mode = str(job.get("wakeMode", "now")).strip() or "now"
    if session_target == "main" and wake_mode == "now":
        print("yes")
        raise SystemExit(0)
print("no")
PY
)

    if [ "${NEEDS_HEARTBEAT}" = "error" ]; then
        check_fail "workspace/automation/cron_jobs.json is invalid"
    elif [ "${NEEDS_HEARTBEAT}" = "yes" ]; then
        if command -v openclaw >/dev/null 2>&1; then
            HEARTBEAT_CADENCE=$(openclaw config get agents.defaults.heartbeat.every 2>/dev/null || true)
            if [ "${HEARTBEAT_CADENCE}" = "0m" ]; then
                check_fail "heartbeat.every=0m while main/wake=now cron jobs are configured"
            elif [ -n "${HEARTBEAT_CADENCE}" ]; then
                check_pass
            else
                check_warn "Could not read heartbeat cadence from openclaw config"
            fi
        else
            check_warn "openclaw CLI missing; heartbeat invariant not evaluated"
        fi
    else
        check_pass
    fi
else
    check_warn "No cron template file; heartbeat invariant skipped"
fi

# ============================================
# 9. BRANCH PROTECTION (local check)
# ============================================
echo "[9/9] Checking branch state..."

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
    check_warn "Currently on protected branch: $CURRENT_BRANCH"
else
    echo "    Current branch: $CURRENT_BRANCH"
    check_pass
fi

# ============================================
# SUMMARY
# ============================================
echo ""
echo "=========================================="

if [ $FAILURES -gt 0 ]; then
    echo -e "${RED}  REGRESSION FAILED${NC}"
    echo "  Failures: $FAILURES"
    echo "  Warnings: $WARNINGS"
    echo ""
    echo "  Fix all failures before admission."
    echo "=========================================="
    exit 1
else
    echo -e "${GREEN}  REGRESSION PASSED${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo "  Warnings: $WARNINGS (review recommended)"
    fi
    echo "=========================================="
    exit 0
fi
