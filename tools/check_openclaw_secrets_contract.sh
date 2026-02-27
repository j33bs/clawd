#!/usr/bin/env bash
set -euo pipefail

CFG="${HOME}/.openclaw/openclaw.json"

if [[ ! -f "$CFG" ]]; then
  echo "FAIL: missing config $CFG"
  exit 1
fi

python3 - <<'PY'
import json, pathlib, sys

cfg = pathlib.Path.home()/".openclaw"/"openclaw.json"
d = json.loads(cfg.read_text())

def fail(msg):
  print(f"FAIL: {msg}")
  sys.exit(1)

models = d.get("models") or {}
providers = models.get("providers") or {}
groq = providers.get("groq") or {}

api = groq.get("apiKey")
if not isinstance(api, dict):
  fail("models.providers.groq.apiKey must be a SecretRef object (dict), not plaintext/string/null")

for k in ("source", "provider", "id"):
  if k not in api:
    fail(f"models.providers.groq.apiKey missing field: {k}")

if api.get("source") != "env":
  fail("models.providers.groq.apiKey.source must be 'env'")
if api.get("provider") != "groq":
  fail("models.providers.groq.apiKey.provider must be 'groq'")
if api.get("id") != "GROQ_API_KEY":
  fail("models.providers.groq.apiKey.id must be 'GROQ_API_KEY'")

secrets = d.get("secrets") or {}
sprov = (secrets.get("providers") or {}).get("groq") or {}

if (sprov.get("source") or "env") != "env":
  fail("secrets.providers.groq.source must be 'env'")

allow = sprov.get("allowlist") or []
if isinstance(allow, str):
  allow = [x.strip() for x in allow.split(",") if x.strip()]
if not isinstance(allow, list):
  fail("secrets.providers.groq.allowlist must be a list or comma-separated string")

if "GROQ_API_KEY" not in [str(x) for x in allow]:
  fail("secrets.providers.groq.allowlist must include 'GROQ_API_KEY'")

print("PASS: secrets contract holds (Groq SecretRef inline + allowlisted; no plaintext).")
PY
