#!/bin/bash
set -e

python3 workspace/scripts/intent_failure_scan.py --max-files 1 --max-errors 1 --stdout > /dev/null
python3 workspace/scripts/test_intent_failure_taxonomy.py > /dev/null

echo "ok"
