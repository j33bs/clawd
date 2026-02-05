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
echo "[1/7] Checking constitutional invariants..."

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
echo "[2/7] Verifying governance substrate..."

if [ -f "workspace/governance/GOVERNANCE_LOG.md" ]; then
    check_pass
else
    check_fail "Governance log missing"
fi

# ============================================
# 3. SECRET SCAN (tracked files)
# ============================================
echo "[3/7] Scanning for secrets in tracked files..."

# Get list of tracked files
TRACKED_FILES=$(git ls-files 2>/dev/null || echo "")

SECRET_FOUND=0
for file in $TRACKED_FILES; do
    # Skip markdown, templates, and gitignore
    if [[ "$file" == *.md ]] || [[ "$file" == *.template ]] || [[ "$file" == .gitignore ]]; then
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
echo "[4/7] Checking for forbidden files..."

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
echo "[5/7] Verifying git hooks..."

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
    check_fail "Git hooks not properly installed"
fi

# ============================================
# 6. DOCUMENTATION COMPLETENESS
# ============================================
echo "[6/7] Checking documentation completeness..."

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
# 7. BRANCH PROTECTION (local check)
# ============================================
echo "[7/7] Checking branch state..."

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
