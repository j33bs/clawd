# System-2 Audit Free Ladder (Gemini -> Qwen -> Groq -> Ollama)

## Goal
Make System-2 audit/governance/security intents route on a free ladder:
1. `google-gemini-cli`
2. `qwen-portal`
3. `groq`
4. `ollama` (mandatory local floor, always last)

OpenAI/Codex lanes are not referenced in the intent routing orders.

## Repo Canonical Config
- Policy: `/Users/heathyeager/clawd/workspace/policy/llm_policy.json`
  - `routing.free_order = ["google-gemini-cli","qwen-portal","groq","ollama"]`
  - `routing.intents.{system2_audit,governance,security}.order` matches the same list
  - `allowPaid=false` for these intents
- Canonical model roster: `/Users/heathyeager/clawd/agents/main/agent/models.json`
  - Providers: `google-gemini-cli`, `qwen-portal`, `groq`, `ollama`
  - Ollama is no-auth (no sentinel `apiKey`).
  - Groq is enabled `"auto"` and references env `${GROQ_API_KEY}` (no key material committed).

## Repair Scripts (Backup-First)
Run these when the agent is stuck in "All models failed" with cooldown/auth churn:

```bash
bash /Users/heathyeager/clawd/scripts/system2_repair_agent_models.sh
bash /Users/heathyeager/clawd/scripts/system2_repair_agent_auth_profiles.sh
```

What they do (secret-safe):
- Copy repo-canonical `agents/main/agent/models.json` into runtime model rosters:
  - `~/.clawdbot/agents/main/agent/models.json`
  - `~/.clawd/agents/main/agent/models.json`
- Scrub OpenAI/Codex model ids (prefixes `openai/` and `openai-codex/`) and remove provider lanes `openai*` + `system2-litellm` from runtime rosters.
- Ensure runtime `auth-profiles.json` has stubs (no secrets) for:
  - `google-gemini-cli:default` (env `GEMINI_API_KEY`)
  - `groq:default` (env `GROQ_API_KEY`)
  - `qwen-portal:default` (oauth stub; operator must populate via OpenClaw auth tooling)
  - `ollama:default` (type `none`)
- Reset persisted cooldown/circuit-like state files under the runtime agent dirs (backup-first, overwrite with `{}`).

## Operator Auth Setup (No Secrets In Repo)
- Gemini: set `GEMINI_API_KEY` in your environment or your OpenClaw secrets backend.
- Groq: set `GROQ_API_KEY` in your environment or your OpenClaw secrets backend.
- Qwen portal: populate the `qwen-portal:default` OAuth profile using your OpenClaw auth tooling (e.g., `openclaw agents add ...` flow).

## Verification (Names/Booleans Only)
```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path.home()/'.clawdbot/agents/main/agent/models.json'
j = json.loads(p.read_text())
providers = j.get('providers') or {}
print('providers=', sorted(providers.keys()))
print('has_openai_provider=', any(k in providers for k in ('openai','openai-codex','openai_codex')))
print('has_system2_litellm=', 'system2-litellm' in providers)
PY
```

## Gateway Runbook (macOS)
If the gateway is not installed/loaded:

```bash
openclaw gateway install
openclaw gateway start
openclaw status
openclaw logs --follow
```
