#!/bin/bash
set -e

python3 - <<'PY'
import json
import sys
from pathlib import Path

failures = []

def load(path):
    p = Path(path)
    if not p.exists():
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_groq(path, provider):
    if not provider:
        return
    if provider.get('enabled') not in (False, 'false', 'False'):
        failures.append(f"{path}: groq.enabled must be false")
    if provider.get('apiKey'):
        failures.append(f"{path}: groq.apiKey must be empty (no secrets)")

# workspace/policy/system_map.json
system_map = load('workspace/policy/system_map.json') or {}
nodes = system_map.get('nodes', {})
if 'dali' not in nodes or 'c_lawd' not in nodes:
    failures.append('workspace/policy/system_map.json: expected nodes dali and c_lawd')

# openclaw.json (optional in repo)
root = load('openclaw.json') or {}
if root:
    providers = root.get('models', {}).get('providers', {})
    check_groq('openclaw.json', providers.get('groq'))

    node_id = root.get('node', {}).get('id')
    if not node_id:
        failures.append('openclaw.json: node.id must be set (or rely on default dali outside tracked config)')
else:
    print('WARN: openclaw.json not found in repo; skipping repo-local node.id enforcement')

# agents/main/agent/models.json
main = load('agents/main/agent/models.json') or {}
check_groq('agents/main/agent/models.json', main.get('providers', {}).get('groq'))

# claude-code ollama baseUrl
claude = load('agents/claude-code/agent/models.json') or {}
ollama = claude.get('providers', {}).get('ollama', {})
base = ollama.get('baseUrl', '')
if base and not base.endswith('/v1'):
    failures.append('agents/claude-code/agent/models.json: ollama.baseUrl must end with /v1')

if failures:
    for f in failures:
        print(f"FAIL: {f}")
    sys.exit(1)

print('ok')
PY
