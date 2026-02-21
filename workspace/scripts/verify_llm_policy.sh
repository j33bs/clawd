#!/bin/bash
set -e

python3 - <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

path = Path(os.environ.get('OPENCLAW_VERIFY_LLM_POLICY_PATH', 'workspace/policy/llm_policy.json'))
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

provider_ids = set(providers.keys())


def load_catalog_provider_ids():
    try:
        out = subprocess.check_output(
            [
                'node',
                '-e',
                "const { CATALOG } = require('./core/system2/inference/catalog');"
                "for (const p of CATALOG) console.log(p.provider_id);",
            ],
            text=True,
        )
        return {line.strip() for line in out.splitlines() if line.strip()}
    except Exception:
        return set()


catalog_provider_ids = load_catalog_provider_ids()

# Legacy policy IDs mapped to canonical provider IDs.
provider_aliases = {
    'google-gemini-cli': 'gemini',
    'qwen-portal': 'qwen_alibaba',
}


def normalize_provider_id(value):
    if not isinstance(value, str):
        return value
    return provider_aliases.get(value, value)


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
        normalized = normalize_provider_id(entry)
        if normalized not in provider_ids and normalized not in catalog_provider_ids:
            print(
                f'FAIL: routing for {intent_name} references unknown provider '
                f'{entry} (normalized={normalized})'
            )
            sys.exit(1)

for name in free_order:
    normalized = normalize_provider_id(name)
    if normalized not in provider_ids and normalized not in catalog_provider_ids:
        print(f'FAIL: free_order references unknown provider {name} (normalized={normalized})')
        sys.exit(1)

print('ok')
PY
