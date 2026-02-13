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

if data.get('version') != 2:
    print('FAIL: policy version must be 2')
    sys.exit(1)

budgets = data.get('budgets', {})
intents = budgets.get('intents', {})
tiers = budgets.get('tiers', {})
if not intents or not tiers:
    print('FAIL: budgets.intents and budgets.tiers are required')
    sys.exit(1)

for intent_name, intent_budget in intents.items():
    for key in ('dailyTokenBudget', 'dailyCallBudget', 'maxCallsPerRun'):
        val = intent_budget.get(key)
        if not isinstance(val, int) or val <= 0:
            print(f'FAIL: intent {intent_name} budget {key} must be positive int')
            sys.exit(1)

for tier_name, tier_budget in tiers.items():
    for key in ('dailyTokenBudget', 'dailyCallBudget'):
        val = tier_budget.get(key)
        if not isinstance(val, int) or val <= 0:
            print(f'FAIL: tier {tier_name} budget {key} must be positive int')
            sys.exit(1)

routing = data.get('routing', {})
free_order = routing.get('free_order', [])
if not isinstance(free_order, list) or not free_order:
    print('FAIL: routing.free_order must be non-empty list')
    sys.exit(1)

providers = data.get('providers', {})
for name, cfg in providers.items():
    if 'tier' not in cfg:
        print(f'FAIL: provider {name} missing tier')
        sys.exit(1)
    if 'type' not in cfg:
        print(f'FAIL: provider {name} missing type')
        sys.exit(1)

free_order_system1 = routing.get('free_order_system1', None)
if free_order_system1 is not None:
    if not isinstance(free_order_system1, list) or not free_order_system1:
        print('FAIL: routing.free_order_system1 must be non-empty list when present')
        sys.exit(1)

intent_routes = routing.get('intents', {})
if not intent_routes:
    print('FAIL: routing.intents missing')
    sys.exit(1)

for intent_name, route in intent_routes.items():
    order = route.get('order', [])
    if not isinstance(order, list) or not order:
        print(f'FAIL: routing order missing for intent {intent_name}')
        sys.exit(1)
    for entry in order:
        if entry == 'free':
            continue
        if entry not in providers:
            print(f'FAIL: routing for {intent_name} references unknown provider {entry}')
            sys.exit(1)

for name in free_order:
    if name not in providers:
        print(f'FAIL: free_order references unknown provider {name}')
        sys.exit(1)

if isinstance(free_order_system1, list):
    for name in free_order_system1:
        if name not in providers:
            print(f'FAIL: free_order_system1 references unknown provider {name}')
            sys.exit(1)

print('ok')
PY
