# OAuth fix: openai-codex TeamChat

## Phase 0 - Baseline

Commands run:

```bash
git status --porcelain -uall
git rev-parse --short HEAD
python3 -m unittest -q
npm test --silent
```

Baseline snapshot:

- Branch: `fix/oauth-openai-codex-teamchat-20260220`
- HEAD: `e8ad6d7`
- Initial status in clean worktree: clean
- Baseline `python3 -m unittest -q`: fails with pre-existing unrelated errors/failures
- Baseline `npm test --silent`: fails (`FAILURES: 1/38`)

Failure excerpts (baseline/full gate):

```text
ImportError: cannot import name 'cache_epitope' from 'tacti_cr.semantic_immune'
AttributeError: module 'team_chat' has no attribute 'run_multi_agent'
AssertionError: False is not true (test_policy_router_teamchat_intent)
```

```text
npm test --silent
...
FAILURES: 1/38
```

## Phase 1 - Current implementation audit

Inspected:

- `workspace/scripts/policy_router.py`
- `workspace/policy/llm_policy.json`

Findings before fix:

- `openai_gpt53_codex` and `openai_gpt53_codex_spark` were configured as `openai_compatible` against `https://api.openai.com/v1`.
- `policy_router` sent all `openai_compatible` traffic to `/chat/completions`.
- OAuth token resolution for OpenAI Codex path was missing; only env/API key flow was used for non-qwen providers.

## Phase 2 - Official Codex CLI wire evidence

Evidence source:

- Local Codex CLI trace (`RUST_LOG=codex_api=trace,codex_client=trace,reqwest=debug codex exec ...`)
- Auth stores inspected (keys only): `~/.codex/auth.json`, `~/.openclaw/agents/main/agent/auth.json`

Observed wire format (redacted):

- Base URL host: `https://chatgpt.com`
- Endpoint path: `/backend-api/codex/responses`
- Payload keys from CLI trace:
  - `include`, `input`, `instructions`, `model`, `parallel_tool_calls`, `prompt_cache_key`, `reasoning`, `store`, `stream`, `text`, `tool_choice`, `tools`
- Required backend constraints verified manually:
  - `instructions` required
  - `stream` must be `true`

## Phase 3 - Implemented fix

### Files changed

1. `workspace/scripts/policy_router.py`

- Added provider wire discriminator support (`wire`, `endpoint` schema acceptance).
- Added codex OAuth resolution helpers:
  - reads `~/.codex/auth.json` (`tokens.access_token`, optional `tokens.account_id`)
  - fallback to `~/.openclaw/agents/main/agent/auth.json` (`openai-codex.access`)
  - precedence: codex auth file first, then openclaw agent auth file
- Added `_resolve_provider_api_key(provider)` for compatibility and unified token lookup.
- Added `_call_codex_cli_compat(...)`:
  - endpoint: `https://chatgpt.com/backend-api/codex/responses` (configurable)
  - sends codex-compatible body with required fields (`instructions`, `stream=true`, `input`, `reasoning`, `text`, `tools`, etc.)
  - sends headers:
    - `Authorization: Bearer <token>`
    - `ChatGPT-Account-Id` when available
    - `Content-Type`, `Accept`, `User-Agent`
  - parses SSE response events deterministically (`response.output_text.delta` + `response.completed`)
  - maps errors with structured diagnostics:
    - `401/403 -> auth_forbidden`
    - `500+ -> request_http_5xx`
- Added injectable HTTP seam (`PolicyRouter(..., http_post=...)`) for deterministic unit tests without network.
- Routed `wire=codex_cli_compat` providers to `_call_codex_cli_compat`; left other providers on existing path.

2. `workspace/policy/llm_policy.json`

- Updated providers `openai_gpt53_codex` and `openai_gpt53_codex_spark`:
  - `baseUrl`: `https://chatgpt.com`
  - `endpoint`: `/backend-api/codex/responses`
  - `wire`: `codex_cli_compat`
  - `auth.type`: `oauth_codex`

3. `tests_unittest/test_openai_codex_oauth_wire.py` (new)

- Deterministic tests for:
  - oauth token path precedence (`~/.codex` then `~/.openclaw`)
  - codex endpoint selection and request headers/payload shape
  - error mapping (`403`, `500`)
  - router dispatch through codex wire mode with mocked HTTP

## Phase 4 - Verification

Targeted tests:

```bash
python3 -m unittest -q tests_unittest/test_openai_codex_oauth_wire.py
python3 -m unittest -q tests_unittest/test_llm_policy_schema_validation.py
python3 -m py_compile workspace/scripts/policy_router.py tests_unittest/test_openai_codex_oauth_wire.py
```

Outcome:

- New OAuth wire tests: `OK (5 tests)`
- Policy schema validation tests: `OK`
- `py_compile`: `OK`

Manual verifier (updated for codex compat path):

```bash
source /Users/heathyeager/clawd/workspace/venv/bin/activate && python3 - <<'PY'
import sys, json
sys.path.insert(0, '/tmp/wt_oauth_fix/workspace/scripts')
from policy_router import PolicyRouter, _resolve_codex_oauth_context, _call_codex_cli_compat
router = PolicyRouter()
provider = router._provider_cfg('openai_gpt53_codex')
ctx = _resolve_codex_oauth_context(provider)
result = _call_codex_cli_compat(
    provider.get('baseUrl'),
    provider.get('endpoint'),
    ctx,
    'gpt-5.3-codex',
    {'messages': [{'role': 'user', 'content': 'Reply with exactly: hi'}]},
    timeout=30,
)
print(json.dumps({'ok': result.get('ok'), 'reason_code': result.get('reason_code'), 'text_preview': (result.get('text') or '')[:80]}))
PY
```

Manual result (redacted):

```text
{"ok": true, "reason_code": null, "text_preview": "hi"}
```

## Phase 5 - Full gates (repo-wide)

Commands run:

```bash
python3 -m unittest -q
npm test --silent
```

Outcome:

- Full python suite: fails on pre-existing unrelated tests (same family as baseline)
- Full npm suite: fails (`FAILURES: 1/38`) pre-existing

Representative excerpts:

```text
ImportError: cannot import name 'cache_epitope' from 'tacti_cr.semantic_immune'
AttributeError: module 'team_chat' has no attribute 'run_multi_agent'
FAILURES: 1/38
```

## Root cause summary

TeamChat/codex routing was using the wrong wire contract (`api.openai.com/v1/chat/completions` + API-key assumptions). The official Codex OAuth path requires ChatGPT codex backend (`/backend-api/codex/responses`) with required `instructions` and SSE streaming payload/response shape. Implementing a dedicated `codex_cli_compat` wire mode fixed the OAuth request path and removed the 403/500/400 class mismatch caused by contract drift.
