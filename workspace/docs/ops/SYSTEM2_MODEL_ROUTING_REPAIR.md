# System-2 Model Routing Repair (Free Ladder + Mandatory Local Floor)

## Symptom
System-2 audit/governance tasks fail with errors like:
- `All models failed (...)` mentioning only OAuth/API-key providers (e.g. Anthropic/Gemini/OpenAI), and not mentioning local models.

## One-Command Repair (Backs Up First)
This resets the runtime agent model roster to the repo-canonical list and clears persisted cooldown/circuit state (backup-first).

```bash
bash scripts/system2_repair_agent_models.sh
bash scripts/system2_repair_agent_auth_profiles.sh
```

What it does (safe, no secret printing):
1. Copies `agents/main/agent/models.json` into:
   - `~/.clawdbot/agents/main/agent/models.json`
   - `~/.clawd/agents/main/agent/models.json` (if used on this machine)
2. Removes any accidental `openai*` / `openai-codex*` provider/model entries from the runtime JSON.
3. Resets cooldown/circuit/resiliency state JSON files under the runtime agent dir(s) by backing them up and overwriting with `{}`.

## Verify Runtime Models (No OAuth)
Show the runtime model file header:

```bash
cat ~/.clawdbot/agents/main/agent/models.json | head
```

Assert there are no OpenAI/Codex providers present (prints only boolean-ish results):

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path.home() / ".clawdbot/agents/main/agent/models.json"
j = json.loads(p.read_text())
providers = j.get("providers") or {}
bad = [k for k in providers.keys() if k in ("openai", "openai-codex", "openai_codex")]
print("has_openai_or_codex_provider=", bool(bad))
print("bad_provider_keys_count=", len(bad))
PY
```

## Routing Policy (Free Ladder + Local Floor)
`workspace/policy/llm_policy.json` is configured so governance/security/audit intents route on a free ladder:
1. `google-gemini-cli`
2. `qwen-portal`
3. `groq`
4. `ollama` (mandatory local floor, always last)

Cloud use is still possible only if explicitly enabled + keyed, and is out of scope for this doc.

## Acceptance Criteria (Precise)
- Provider SET after repair (order irrelevant):
  - `{google-gemini-cli, qwen-portal, groq, ollama}`
- Routing ORDER (policy):
  - `["google-gemini-cli","qwen-portal","groq","ollama"]`
- No `system2-litellm` anywhere in intent routing orders.
- Ollama must be no-auth (no sentinel `apiKey`, no required API key env var).

## Gateway Service Runbook (macOS)
If the gateway is not installed, install and start it:

```bash
openclaw gateway install
openclaw gateway start
openclaw status
openclaw logs --follow
```
