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
    # Groq is allowed for the System-2 free ladder, but must never contain key material.
    # Accept either a missing apiKey field or a reference to the env var name.
    api_key = provider.get('apiKey')
    if api_key not in (None, '', 'GROQ_API_KEY'):
        failures.append(f\"{path}: groq.apiKey must be empty or 'GROQ_API_KEY' (no secrets)\")

# openclaw.json (optional; may not exist in this repo)
try:
    root = load('openclaw.json')
    providers = root.get('models', {}).get('providers', {})
    check_groq('openclaw.json', providers.get('groq'))
except FileNotFoundError:
    pass

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
