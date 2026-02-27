# DALI Fix: Runtime Hardening Anthropic Key Conditional

- UTC timestamp: 2026-02-27T08:34:27Z
- Repo root: /home/jeebs/src/clawd
- Git HEAD (pre-commit): 94771a975589c25ec5dca82ab468cf85e683c31f

## Problem Statement
Built runtime failed fast when ANTHROPIC_API_KEY was unset, regardless of provider enablement.

## Original Stack Trace (pre-fix repro)
Command:
```bash
unset ANTHROPIC_API_KEY
node .runtime/openclaw/dist/index.js --version
```

Output:
```text
file:///home/jeebs/src/clawd/.runtime/openclaw/dist/hardening/config.mjs:102
    throw new Error(`Invalid runtime hardening configuration:\n- ${errors.join('\n- ')}`);
          ^

Error: Invalid runtime hardening configuration:
- ANTHROPIC_API_KEY: required non-empty value is missing
    at validateConfig (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/hardening/config.mjs:102:11)
    at getConfig (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/hardening/config.mjs:123:17)
    at file:///home/jeebs/src/clawd/.runtime/openclaw/dist/runtime_hardening_overlay.mjs:360:14
    at ModuleJob.run (node:internal/modules/esm/module_job:343:25)
    at async onImport.tracePromise.__proto__ (node:internal/modules/esm/loader:665:26)
    at async asyncRunEntryPointWithESMLoader (node:internal/modules/run_main:117:5)

Node.js v22.22.0
```

## Root Cause
- Source validator in workspace/runtime_hardening/src/config.mjs unconditionally required non-empty ANTHROPIC_API_KEY.
- No provider enablement check was performed before validating the key.

## Source-of-Truth Paths Found
- workspace/runtime_hardening/src/config.mjs
- workspace/runtime_hardening/tests/config.test.mjs
- workspace/scripts/rebuild_runtime_openclaw.sh (copies source into .runtime/openclaw/dist/hardening/)

## Changes Made (no dist edits)
1. workspace/runtime_hardening/src/config.mjs
- Added provider parsing for OPENCLAW_PROVIDER_ALLOWLIST.
- Added isAnthropicEnabled(env) check using OPENCLAW_PROVIDER_ALLOWLIST, OPENCLAW_DEFAULT_PROVIDER, and OPENCLAW_DEFAULT_MODEL.
- Made ANTHROPIC_API_KEY required only when Anthropic is enabled.

2. workspace/runtime_hardening/tests/config.test.mjs
- Added PASS case: anthropic disabled + key missing => no throw.
- Added FAIL case: anthropic enabled + key missing => throws with clear message.

## Test Evidence
### Targeted config test
```bash
node --test workspace/runtime_hardening/tests/config.test.mjs
```
```text
TAP version 13
# Subtest: workspace/runtime_hardening/tests/config.test.mjs
ok 1 - workspace/runtime_hardening/tests/config.test.mjs
  ---
  duration_ms: 36.725692
  type: 'test'
  ...
1..1
# tests 1
# suites 0
# pass 1
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 42.933423
```

### Full hardening suite
```bash
npm run test:hardening
```
```text

> openclaw@0.0.0 test:hardening
> node --test workspace/runtime_hardening/tests/*.test.mjs

TAP version 13
# Subtest: workspace/runtime_hardening/tests/config.test.mjs
ok 1 - workspace/runtime_hardening/tests/config.test.mjs
  ---
  duration_ms: 38.384973
  type: 'test'
  ...
# Subtest: workspace/runtime_hardening/tests/fs_sandbox.test.mjs
ok 2 - workspace/runtime_hardening/tests/fs_sandbox.test.mjs
  ---
  duration_ms: 36.814544
  type: 'test'
  ...
# Subtest: workspace/runtime_hardening/tests/mcp_singleflight.test.mjs
ok 3 - workspace/runtime_hardening/tests/mcp_singleflight.test.mjs
  ---
  duration_ms: 44.616078
  type: 'test'
  ...
# Subtest: workspace/runtime_hardening/tests/network_enum.test.mjs
ok 4 - workspace/runtime_hardening/tests/network_enum.test.mjs
  ---
  duration_ms: 43.52239
  type: 'test'
  ...
# Subtest: workspace/runtime_hardening/tests/outbound_sanitize.test.mjs
ok 5 - workspace/runtime_hardening/tests/outbound_sanitize.test.mjs
  ---
  duration_ms: 36.058532
  type: 'test'
  ...
# Subtest: workspace/runtime_hardening/tests/retry_backoff.test.mjs
ok 6 - workspace/runtime_hardening/tests/retry_backoff.test.mjs
  ---
  duration_ms: 33.833278
  type: 'test'
  ...
# Subtest: workspace/runtime_hardening/tests/session.test.mjs
ok 7 - workspace/runtime_hardening/tests/session.test.mjs
  ---
  duration_ms: 35.415974
  type: 'test'
  ...
# Subtest: workspace/runtime_hardening/tests/status_hint.test.mjs
ok 8 - workspace/runtime_hardening/tests/status_hint.test.mjs
  ---
  duration_ms: 32.141581
  type: 'test'
  ...
# Subtest: workspace/runtime_hardening/tests/telegram_outbound_sanitize.test.mjs
ok 9 - workspace/runtime_hardening/tests/telegram_outbound_sanitize.test.mjs
  ---
  duration_ms: 35.342868
  type: 'test'
  ...
# Subtest: workspace/runtime_hardening/tests/telegram_reply_mode.test.mjs
ok 10 - workspace/runtime_hardening/tests/telegram_reply_mode.test.mjs
  ---
  duration_ms: 35.960896
  type: 'test'
  ...
# Subtest: workspace/runtime_hardening/tests/tool_sanitize.test.mjs
ok 11 - workspace/runtime_hardening/tests/tool_sanitize.test.mjs
  ---
  duration_ms: 45.093581
  type: 'test'
  ...
1..11
# tests 11
# suites 0
# pass 11
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 67.124557
```

## Rebuild Evidence
```bash
bash workspace/scripts/rebuild_runtime_openclaw.sh
```
```text
repo_sha=94771a9
source=/usr/lib/node_modules/openclaw
target=/home/jeebs/src/clawd/.runtime/openclaw
memory_snapshot={"snapshot_dir": "/home/jeebs/src/clawd/workspace/state_runtime/memory/snapshots/20260227T083335Z-runtime-rebuild", "manifest_path": "/home/jeebs/src/clawd/workspace/state_runtime/memory/snapshots/20260227T083335Z-runtime-rebuild/manifest.json", "file_count": 4}
marker_check_runtime_dist:
/home/jeebs/src/clawd/.runtime/openclaw/dist/index.js:2:import "./runtime_hardening_overlay.mjs";
/home/jeebs/src/clawd/.runtime/openclaw/dist/entry.js:2:import "./runtime_hardening_overlay.mjs";
/home/jeebs/src/clawd/.runtime/openclaw/dist/hardening/config.mjs:129:    throw new Error(`Invalid runtime hardening configuration:\n- ${errors.join('\n- ')}`);
/home/jeebs/src/clawd/.runtime/openclaw/dist/runtime_hardening_overlay.mjs:411:  runtimeLogger.info('runtime_hardening_initialized', {
```

## Verification Evidence
### Runtime versions
```bash
node --version
openclaw --version
```
```text
v22.22.0
2026.2.25 build_sha=237e312 build_time=2026-02-24T06:23:42Z
```

### Case A: Anthropic disabled, key missing (PASS)
```bash
unset ANTHROPIC_API_KEY
OPENCLAW_PROVIDER_ALLOWLIST=local_vllm node .runtime/openclaw/dist/index.js --version
```
Exit code: 0
```text
{"ts":"2026-02-27T08:33:37.575Z","level":"info","msg":"outbound_fetch_sanitizer_installed","service":"runtime-hardening","module":"runtime-hardening-overlay"}
{"ts":"2026-02-27T08:33:37.575Z","level":"info","msg":"runtime_hardening_initialized","service":"runtime-hardening","module":"runtime-hardening-overlay","config":{"anthropicApiKey":"<redacted>","nodeEnv":"development","workspaceRoot":"/home/jeebs/src/clawd","agentWorkspaceRoot":"/home/jeebs/src/clawd/.agent_workspace","skillsRoot":"/home/jeebs/src/clawd/skills","sessionTtlMs":21600000,"sessionMax":50,"historyMaxMessages":200,"mcpServerStartTimeoutMs":30000,"logLevel":"info","fsAllowOutsideWorkspace":false,"telegramReplyMode":"never"}}
2026.2.25
```

### Case B: Anthropic enabled, key missing (FAIL expected)
```bash
unset ANTHROPIC_API_KEY
OPENCLAW_PROVIDER_ALLOWLIST=anthropic node .runtime/openclaw/dist/index.js --version
```
Exit code: 1
```text
file:///home/jeebs/src/clawd/.runtime/openclaw/dist/hardening/config.mjs:129
    throw new Error(`Invalid runtime hardening configuration:\n- ${errors.join('\n- ')}`);
          ^

Error: Invalid runtime hardening configuration:
- ANTHROPIC_API_KEY: required non-empty value is missing
    at validateConfig (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/hardening/config.mjs:129:11)
    at getConfig (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/hardening/config.mjs:150:17)
    at file:///home/jeebs/src/clawd/.runtime/openclaw/dist/runtime_hardening_overlay.mjs:360:14
    at ModuleJob.run (node:internal/modules/esm/module_job:343:25)
    at async onImport.tracePromise.__proto__ (node:internal/modules/esm/loader:665:26)
    at async asyncRunEntryPointWithESMLoader (node:internal/modules/run_main:117:5)

Node.js v22.22.0
```

## Rollback Instructions
```bash
git revert <commit_sha>
bash workspace/scripts/rebuild_runtime_openclaw.sh
```
