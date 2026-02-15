# System-2 Model Routing Repair (No OAuth / Local Floor)

## Symptom
System-2 audit/governance tasks fail with errors like:
- `All models failed (...)` mentioning only OAuth/API-key providers (e.g. Anthropic/Gemini/OpenAI), and not mentioning local models.

## One-Command Repair (Backs Up First)
This resets the runtime agent model roster to the repo-canonical list and clears persisted cooldown/circuit state (backup-first).

```bash
bash scripts/system2_repair_agent_models.sh
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

## Routing Policy (Local Floor)
`workspace/policy/llm_policy.json` is configured so governance/security/audit intents route local-first (Ollama), with Groq as a fallback. OAuth/OpenAI lanes are disabled and removed from those intent orders.

Cloud use is still possible only if explicitly enabled + keyed, and is out of scope for this doc.

