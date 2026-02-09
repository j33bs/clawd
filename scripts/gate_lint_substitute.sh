#!/bin/sh
set -eu

node scripts/verify_model_routing.js
node tests/sys_acceptance.test.js
node scripts/sys_evolution_self_test.js

echo "LINT_SUBSTITUTE=PASS"
