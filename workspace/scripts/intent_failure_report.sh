#!/bin/bash
set -e

DATE=$(date +%F)
OUT="workspace/handoffs/intent_failures_${DATE}.md"
python3 workspace/scripts/intent_failure_scan.py --out "$OUT"

echo "wrote ${OUT}"
