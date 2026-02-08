#!/bin/bash
set -e

python3 - <<'PY'
import json
import sys

failures = []

def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_groq(path, provider):
    if not provider:
        return
    if provider.get('enabled') not in (False, 'false', 'False'):
        failures.append(f"{path}: groq.enabled must be false")
    if provider.get('apiKey'):
        failures.append(f"{path}: groq.apiKey must be empty (no secrets)")

# openclaw.json
root = load('openclaw.json')
providers = root.get('models', {}).get('providers', {})
check_groq('openclaw.json', providers.get('groq'))

# agents/main/agent/models.json
main = load('agents/main/agent/models.json')
check_groq('agents/main/agent/models.json', main.get('providers', {}).get('groq'))

# claude-code ollama baseUrl
claude = load('agents/claude-code/agent/models.json')
ollama = claude.get('providers', {}).get('ollama', {})
base = ollama.get('baseUrl', '')
if not base.endswith('/v1'):
    failures.append('agents/claude-code/agent/models.json: ollama.baseUrl must end with /v1')

if failures:
    for f in failures:
        print(f"FAIL: {f}")
    sys.exit(1)

print('ok')
PY
