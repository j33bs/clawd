#!/bin/bash
set -e

python3 - <<'PY'
import json
import sys
from pathlib import Path

path = Path('workspace/policy/llm_policy.json')
if not path.exists():
    print('FAIL: policy file missing')
    sys.exit(1)

try:
    data = json.loads(path.read_text(encoding='utf-8'))
except Exception as exc:
    print(f'FAIL: policy file invalid json: {exc}')
    sys.exit(1)

budgets = data.get('budgets', {}).get('itc_classify', {})
for key in ('dailyTokenBudget', 'dailyCallBudget', 'maxCallsPerRun'):
    val = budgets.get(key)
    if not isinstance(val, int) or val <= 0:
        print(f'FAIL: budget {key} must be positive int')
        sys.exit(1)

routing = data.get('routing', {}).get('itc_classify', {})
order = routing.get('order', [])
if not isinstance(order, list) or not order:
    print('FAIL: routing order must be non-empty list')
    sys.exit(1)

allowed = {'groq', 'qwen', 'ollama'}
unknown = [x for x in order if x not in allowed]
if unknown:
    print(f'FAIL: routing order contains unknown providers: {unknown}')
    sys.exit(1)

providers = data.get('providers', {})
for name in order:
    if name not in providers:
        print(f'FAIL: provider missing: {name}')
        sys.exit(1)

print('ok')
PY
