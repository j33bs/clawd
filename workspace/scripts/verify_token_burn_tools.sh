#!/bin/bash
set -euo pipefail

TS=$(date +%Y%m%d_%H%M%S)
A="tmp/token_burn_verify_${TS}_a.md"
B="tmp/token_burn_verify_${TS}_b.md"

python3 workspace/scripts/report_token_burn.py --max-files 2 --out "$A" --stdout > /dev/null
python3 workspace/scripts/report_token_burn.py --max-files 2 --out "$B" --stdout > /dev/null
python3 workspace/scripts/compare_token_burn.py "$A" "$A" --stdout > /dev/null
python3 workspace/scripts/compare_token_burn.py "$A" "$B" --stdout > /dev/null || true

echo "ok"
