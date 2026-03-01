#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[security-gates] running gateway hardening unit tests"
node --test tests/gateway_security_hardening_patch.test.js

echo "[security-gates] verifying runtime patch is present"
bash tools/apply_gateway_security_hardening.sh --check

echo "[security-gates] verifying auth rate limiter getMetrics() callable (LOG-02, LOG-06)"
node --input-type=module <<'EOF'
import { createAuthAttemptLimiter } from './tools/gateway_security_hardening_patch.mjs';
const limiter = createAuthAttemptLimiter({ maxAttempts: 5, windowMs: 60000 });
const metrics = limiter.getMetrics();
if (typeof metrics.rate_limit_hits_total !== 'number') throw new Error('rate_limit_hits_total must be a number');
if (typeof metrics.rate_limit_active_windows !== 'number') throw new Error('rate_limit_active_windows must be a number');
if (typeof metrics.ts !== 'number') throw new Error('ts must be a number');
process.stdout.write('[security-gates] auth limiter getMetrics() OK\n');
EOF

echo "[security-gates] PASS"
