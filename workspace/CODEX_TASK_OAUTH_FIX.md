# Codex Task: Fix OpenAI OAuth for TeamChat

## Context

TeamChat is currently failing because OpenAI OAuth returns 403 Forbidden when calling the API. The OAuth token is valid (from auth.json) but something in the request is wrong.

## Current State

1. **Auth is configured**: OAuth token exists in `~/.openclaw/agents/main/agent/auth.json` under `openai-codex`
2. **Token is valid**: Contains correct scopes (openid, profile, email, offline_access) and audience (api.openai.com/v1)
3. **Current error**: 403 Forbidden when making API calls

## What We've Tried

- Standard endpoint (`api.openai.com/v1/chat/completions`) → 500 Internal Error
- ChatGPT backend (`chatgpt.com/backend-api/conversation`) → 403 Forbidden
- Different models (gpt-4o-mini, gpt-5.3-codex, etc.) → Same errors

## Your Task

### 1. Audit the Current Implementation

Review these files:
- `workspace/scripts/policy_router.py` - How OAuth tokens are resolved and used
- `workspace/policy/llm_policy.json` - Provider configurations

### 2. Identify the Root Cause

The Nature paper "Arousal as universal embedding" shows OpenAI Codex uses a different backend than the standard API. Research how the official Codex CLI handles OAuth authentication:
- What endpoint does it call?
- What headers/parameters does it use?
- Is there a specific authentication flow?

### 3. Fix the Implementation

Possible approaches:
- Add a new provider type for Codex-backed models
- Implement the correct endpoint/headers in policy_router.py
- Check if there's a specific API for ChatGPT subscription access

### 4. Test the Fix

Run TeamChat or a simple test to verify the fix works:
```bash
cd /Users/heathyeager/clawd
source workspace/venv/bin/activate
python3 -c "
import sys
sys.path.insert(0, 'workspace/scripts')
from policy_router import _call_openai_compatible, PolicyRouter
router = PolicyRouter()
provider = router._provider_cfg('openai-codex')
from policy_router import _resolve_provider_api_key
api_key = _resolve_provider_api_key(provider)
result = _call_openai_compatible(
    provider['baseUrl'],
    api_key,
    'gpt-5.2-codex',
    {'messages': [{'role': 'user', 'content': 'hi'}]},
    15
)
print(f'Result: {result}')
"
```

## Success Criteria

- TeamChat can make successful API calls using OAuth
- No more 403/500 errors
- Architecture review can run successfully

## References

- OpenAI Codex Auth Docs: https://developers.openai.com/codex/auth/
- QMD MCP is running on port 8181 for workspace search
- KB synced with research docs including TACTI architecture
