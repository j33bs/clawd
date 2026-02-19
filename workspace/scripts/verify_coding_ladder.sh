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

data = json.loads(path.read_text(encoding='utf-8'))
routing = data.get('routing', {}).get('intents', {})
order = routing.get('coding', {}).get('order', [])
expected = ["free", "openai_auth_brain", "openai_auth_muscle", "claude_auth", "grok_api", "openai_api", "claude_api"]
if order != expected:
    print(f'FAIL: coding ladder mismatch: {order} != {expected}')
    sys.exit(1)

print('ok')
PY
