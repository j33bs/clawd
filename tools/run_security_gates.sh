#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[security-gates] running gateway hardening unit tests"
node --test tests/gateway_security_hardening_patch.test.js

echo "[security-gates] verifying runtime patch is present"
bash tools/apply_gateway_security_hardening.sh --check

echo "[security-gates] PASS"
