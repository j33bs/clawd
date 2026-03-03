# Quick Fix: OpenAI OAuth 403 Error

## Problem
TeamChat can't make API calls - getting 403 Forbidden with valid OAuth token.

## Token Info
- Source: `~/.openclaw/agents/main/agent/auth.json` → `openai-codex` profile
- Token type: JWT (OAuth)
- Scopes: openid, profile, email, offline_access

## Tested Endpoints
1. `https://api.openai.com/v1/chat/completions` → 500 Internal Error
2. `https://chatgpt.com/backend-api/conversation` → 403 Forbidden

## What Needs Fixing
The policy_router.py needs to call the correct endpoint with correct headers for ChatGPT OAuth.

## Files to Modify
- `workspace/scripts/policy_router.py` - OAuth resolution and API calls
- `workspace/policy/llm_policy.json` - Provider configs (already has openai-codex)

## Test Command
```bash
cd /Users/heathyeager/clawd && source workspace/venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'workspace/scripts')
from policy_router import _call_openai_compatible, PolicyRouter
router = PolicyRouter()
p = router._provider_cfg('openai-codex')
from policy_router import _resolve_provider_api_key
k = _resolve_provider_api_key(p)
r = _call_openai_compatible(p['baseUrl'], k, 'gpt-5.2-codex', {'messages':[{'role':'user','content':'hi'}]}, 15)
print(r)
"
```

## Success
Get `{'ok': True, ...}` instead of 403/500 errors.
