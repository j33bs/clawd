# Codex Task: Fix PolicyRouter OpenAI OAuth Auth Resolution

## Problem
PolicyRouter currently looks for `OPENAI_API_KEY` environment variable when routing to `openai_gpt52_chat` or similar providers. However, OpenClaw stores OpenAI auth as OAuth tokens in `~/.openclaw/agents/main/agent/auth.json`, not env vars.

## Current Behavior
- Config specifies `openai_gpt52_chat` provider
- PolicyRouter tries to use it → checks env var → fails with `missing_api_key`
- Falls back to lower-tier providers

## Expected Behavior
PolicyRouter should detect OAuth tokens in OpenClaw's auth.json and use them when available, instead of requiring raw API keys in env vars.

## Implementation

### File: `workspace/scripts/policy_router.py`

Add a function to resolve OpenAI OAuth tokens:

```python
def _resolve_openai_auth() -> str | None:
    """
    Resolve OpenAI OAuth token from OpenClaw auth.json.
    Returns access token if valid, None otherwise.
    """
    auth_path = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth.json"
    if not auth_path.exists():
        return None

    try:
        auth_data = json.loads(auth_path.read_text())
        openai_entry = auth_data.get("openai-codex") or auth_data.get("openai")
        if not openai_entry:
            return None

        access_token = openai_entry.get("access")
        expires = openai_entry.get("expires")

        # Check if token is expired
        if expires and isinstance(expires, (int, float)):
            if expires < (time.time() * 1000):
                # Token expired - need refresh (not implemented yet)
                return None

        return access_token
    except Exception:
        return None
```

### Modify Provider Resolution

When resolving `openai_gpt52_chat` (or any OpenAI provider), check:
1. First: `OPENAI_API_KEY` env var (backwards compatible)
2. Second: OpenClaw OAuth token via `_resolve_openai_auth()`
3. If neither, mark as `missing_api_key`

### Update Provider Credentials

The provider initialization should accept OAuth tokens:

```python
# In provider setup
api_key = (
    os.environ.get("OPENAI_API_KEY")
    or _resolve_openai_auth()
)
```

## Files to Modify
- `workspace/scripts/policy_router.py` — add OAuth resolution, update provider setup

## Testing
- Verify `openai_gpt52_chat` works without `OPENAI_API_KEY` env var
- Verify it uses OAuth token from auth.json
- Verify fallback still works when OAuth unavailable

## Priority
High — blocks TeamChat planner from working with GPT-5.2
