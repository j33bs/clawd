#!/bin/bash
# OpenClaw Pre-Admission Verification
# Category: B (Security)
# Extended validation for change admission
#
# Usage: ./workspace/scripts/verify.sh
# Exit: 0 on pass, 1 on failure

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "  OpenClaw Pre-Admission Verification"
echo "=========================================="
echo ""

# ============================================
# Run preflight before regression
# ============================================
echo "[Step 1] Running preflight checks..."
echo ""

if bash ./workspace/scripts/verify_preflight.sh; then
    echo ""
    echo -e "${GREEN}Preflight passed. Continuing verification...${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}Preflight failed. Fix issues before proceeding.${NC}"
    exit 1
fi

# ============================================
# Run regression
# ============================================
echo "[Step 2] Running regression validation..."
echo ""

if ./workspace/scripts/regression.sh; then
    echo ""
    echo -e "${GREEN}Regression passed. Continuing verification...${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}Regression failed. Fix issues before proceeding.${NC}"
    exit 1
fi

FAILURES=0

check_pass() {
    echo -e "${GREEN}  ✓ PASS${NC}"
}

check_fail() {
    echo -e "${RED}  ✗ FAIL: $1${NC}"
    FAILURES=$((FAILURES + 1))
}

# ============================================
# Additional verifications
# ============================================

echo "[Step 3] Checking design brief template..."
if [ -f "workspace/docs/briefs/_TEMPLATE.md" ]; then
    check_pass
else
    check_fail "Design brief template missing"
fi

echo "[Step 4] Checking security documentation..."
SECURITY_DOCS="audit_log credential_rotation"
SECURITY_OK=1
for doc in $SECURITY_DOCS; do
    if [ ! -f "workspace/sources/security/${doc}.md" ]; then
        echo "    Missing: ${doc}.md"
        SECURITY_OK=0
    fi
done

if [ $SECURITY_OK -eq 1 ]; then
    check_pass
else
    check_fail "Security documentation incomplete"
fi

echo "[Step 5] Checking model routing policy..."
if [ -f "workspace/MODEL_ROUTING.md" ]; then
    check_pass
else
    check_fail "MODEL_ROUTING.md missing"
fi

echo "[Step 6] Checking secrets template..."
if [ -f "secrets.env.template" ]; then
    check_pass
else
    check_fail "secrets.env.template missing"
fi

echo "[Step 7] Checking .gitattributes..."
if [ -f ".gitattributes" ]; then
    check_pass
else
    check_fail ".gitattributes missing (drift prevention)"
fi

echo "[Step 8] Checking CONTRIBUTING.md..."
if [ -f "CONTRIBUTING.md" ]; then
    if grep -q "Change Admission Process" CONTRIBUTING.md; then
        check_pass
    else
        check_fail "CONTRIBUTING.md missing admission process"
    fi
else
    check_fail "CONTRIBUTING.md missing"
fi

echo "[Step 9] Checking LLM policy..."
if [ -x "workspace/scripts/verify_llm_policy.sh" ]; then
    if ./workspace/scripts/verify_llm_policy.sh; then
        check_pass
    else
        check_fail "LLM policy verification failed"
    fi
else
    check_fail "verify_llm_policy.sh missing or not executable"
fi

echo "[Step 10] Checking coding ladder..."
if [ -x "workspace/scripts/verify_coding_ladder.sh" ]; then
    if ./workspace/scripts/verify_coding_ladder.sh; then
        check_pass
    else
        check_fail "Coding ladder verification failed"
    fi
else
    check_fail "verify_coding_ladder.sh missing or not executable"
fi

echo "[Step 11] Checking policy router..."
if [ -x "workspace/scripts/verify_policy_router.sh" ]; then
    if ./workspace/scripts/verify_policy_router.sh; then
        check_pass
    else
        check_fail "Policy router verification failed"
    fi
else
    check_fail "verify_policy_router.sh missing or not executable"
fi

echo "[Step 12] Checking intent-failure scan..."
if [ -x "workspace/scripts/verify_intent_failure_scan.sh" ]; then
    if ./workspace/scripts/verify_intent_failure_scan.sh; then
        check_pass
    else
        check_fail "Intent-failure scan verification failed"
    fi
else
    check_fail "verify_intent_failure_scan.sh missing or not executable"
fi

# ============================================
# SUMMARY
# ============================================
echo ""
echo "=========================================="

if [ $FAILURES -gt 0 ]; then
    echo -e "${RED}  VERIFICATION FAILED${NC}"
    echo "  Failures: $FAILURES"
    echo ""
    echo "  Fix all failures before admission."
    echo "=========================================="
    exit 1
else
    echo -e "${GREEN}  VERIFICATION PASSED${NC}"
    echo ""
    echo "  All checks passed. Ready for admission."
    echo "=========================================="
    exit 0
fi
