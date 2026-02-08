#!/bin/bash
set -e

python3 workspace/scripts/intent_failure_scan.py --max-files 1 --max-errors 1 --stdout > /dev/null

echo "ok"
