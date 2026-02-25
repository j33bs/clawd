# Dali MCP Client Hardening Audit

- Timestamp (UTC): 2026-02-25T20:14:42Z
- Branch: `codex/fix/dali-audit-hardening-mcp-client-20260226`
- Scope: Runtime hardening layer + runtime rebuild overlay integration

## Findings -> Remediation Map

### High Priority

- Missing config fail-fast validation
  - Added `workspace/runtime_hardening/src/config.mjs`
  - Enforces required `ANTHROPIC_API_KEY`
  - Validates `NODE_ENV`, numeric limits, and path constraints
  - Emits single clear aggregated error message without exposing secrets

- Session memory growth risk (map/history unbounded)
  - Added `workspace/runtime_hardening/src/session.mjs`
  - `SessionManager` now enforces:
    - TTL eviction (`SESSION_TTL_MS`)
    - max session cap (`SESSION_MAX`)
    - max in-session history (`HISTORY_MAX_MESSAGES`)
  - Includes `closeSession()` and `shutdown()` cleanup

- MCP start race condition risk
  - Added `workspace/runtime_hardening/src/mcp_singleflight.mjs`
  - Keyed singleflight map (`inFlight`) + started handle cache (`running`)
  - Startup timeout (`MCP_SERVER_START_TIMEOUT_MS`)
  - Retries after failure supported (inFlight cleared in `finally`)

### Medium Priority

- No structured logger
  - Added `workspace/runtime_hardening/src/log.mjs`
  - Structured JSON logger with levels + redaction
  - No `console.*` in hardening sources

- Hard-coded workspace paths
  - Added `workspace/runtime_hardening/src/paths.mjs`
  - Config-driven roots: `WORKSPACE_ROOT`, `AGENT_WORKSPACE_ROOT`, `SKILLS_ROOT`
  - Safe directory creation constrained by workspace root by default

- Missing tests
  - Added deterministic tests under `workspace/runtime_hardening/tests/`
  - Covers config validation, session bounds, singleflight, fs sandbox, payload sanitizer, retry/backoff

- package.json hygiene
  - Added `repository`, `bugs`, `homepage`, `engines.node >=20`
  - Added scripts:
    - `test:hardening`
    - `test:hardening:watch`
    - `typecheck:hardening`
    - `runtime:rebuild`

### Security Findings

- Filesystem unrestricted
  - Added `workspace/runtime_hardening/src/security/fs_sandbox.mjs`
  - Rejects traversal/symlink escape outside workspace root by default
  - Escape hatch: `FS_ALLOW_OUTSIDE_WORKSPACE=true`

- Tool payload sanitization missing
  - Added `workspace/runtime_hardening/src/security/tool_sanitize.mjs`
  - Validates tool payload schema/shape and bounded size limits
  - Rejects oversized/deep/non-plain payloads with explicit error codes

### Low Priority

- Retry/backoff missing
  - Added `workspace/runtime_hardening/src/retry_backoff.mjs`
  - Exponential backoff + jitter
  - Retries on 429/5xx
  - Supports `Retry-After`

## Runtime Integration

- Restored `workspace/scripts/rebuild_runtime_openclaw.sh`
- Rebuild now copies runtime + hardening modules and injects:
  - `import "./runtime_hardening_overlay.mjs";` into `.runtime/openclaw/dist/index.js`
- Overlay bootstrap:
  - `workspace/runtime_hardening/overlay/runtime_hardening_overlay.mjs`
  - Initializes validated config, safe dirs, bounded session manager, and helper APIs for singleflight/sanitization/retry

## Config Knobs and Defaults

- `ANTHROPIC_API_KEY` (required)
- `NODE_ENV` default `development` (`development|test|production`)
- `WORKSPACE_ROOT` default `process.cwd()`
- `AGENT_WORKSPACE_ROOT` default `${WORKSPACE_ROOT}/.agent_workspace`
- `SKILLS_ROOT` default `${WORKSPACE_ROOT}/skills`
- `SESSION_TTL_MS` default `21600000`
- `SESSION_MAX` default `50`
- `HISTORY_MAX_MESSAGES` default `200`
- `MCP_SERVER_START_TIMEOUT_MS` default `30000`
- `LOG_LEVEL` default `info`
- `FS_ALLOW_OUTSIDE_WORKSPACE` default `false`

## Security Model Statement

By default, filesystem writes/reads are constrained to `WORKSPACE_ROOT`, path traversal and symlink escape attempts are rejected, and tool payloads are bounded and schema-validated before execution. Operators can opt out with explicit env (`FS_ALLOW_OUTSIDE_WORKSPACE=true`) when needed.

## Verification Commands + Outputs

### 1) Syntax/type gate

```bash
npm run typecheck:hardening
```

```text
> openclaw@0.0.0 typecheck:hardening
> node --check workspace/runtime_hardening/src/*.mjs && node --check workspace/runtime_hardening/src/security/*.mjs && node --check workspace/runtime_hardening/overlay/*.mjs
```

### 2) Unit tests

```bash
npm run test:hardening
```

```text
> openclaw@0.0.0 test:hardening
> node --test workspace/runtime_hardening/tests/*.test.mjs
...
# pass 6
# fail 0
```

### 3) Runtime rebuild + overlay markers

```bash
npm run runtime:rebuild
```

```text
repo_sha=c259368
source=/usr/lib/node_modules/openclaw
target=/home/jeebs/src/clawd/.runtime/openclaw
marker_check_runtime_dist:
/home/jeebs/src/clawd/.runtime/openclaw/dist/index.js:2:import "./runtime_hardening_overlay.mjs";
/home/jeebs/src/clawd/.runtime/openclaw/dist/runtime_hardening_overlay.mjs:48:  runtimeLogger.info('runtime_hardening_initialized', {
```

## Final Verification + Merge-Safety Pass (2026-02-25 UTC)

### A) Runtime liveness sanity checks

#### A1. Overlay marker present

```bash
rg -n "runtime_hardening_overlay" .runtime/openclaw/dist/index.js || true
```

```text
2:import "./runtime_hardening_overlay.mjs";
```

#### A2. Fail-fast config (missing `ANTHROPIC_API_KEY`)

```bash
( unset ANTHROPIC_API_KEY; node .runtime/openclaw/dist/index.js 2>&1 | head -n 50; echo "exit=$?" )
```

```text
file:///home/jeebs/src/clawd/.runtime/openclaw/dist/hardening/config.mjs:91
    throw new Error(`Invalid runtime hardening configuration:\n- ${errors.join('\n- ')}`);
          ^

Error: Invalid runtime hardening configuration:
- ANTHROPIC_API_KEY: required non-empty value is missing
    at validateConfig (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/hardening/config.mjs:91:11)
    at getConfig (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/hardening/config.mjs:111:17)
    at file:///home/jeebs/src/clawd/.runtime/openclaw/dist/runtime_hardening_overlay.mjs:16:18
    at ModuleJob.run (node:internal/modules/esm/module_job:343:25)
    at async onImport.tracePromise.__proto__ (node:internal/modules/esm/loader:665:26)
    at async asyncRunEntryPointWithESMLoader (node:internal/modules/run_main:117:5)

Node.js v22.22.0
exit=1
```

#### A3. No `console.*` in hardening sources

```bash
rg -n "console\.(log|warn|error)" workspace/runtime_hardening/src || true
```

```text
(no matches)
```

### B) Unrelated failing suites analysis

#### B1. Files changed by this branch

```bash
git diff --name-only origin/main...HEAD
```

```text
AGENTS.md
README.md
package.json
workspace/audit/dali_mcp_client_hardening_20260226T201442Z.md
workspace/runtime_hardening/README.md
workspace/runtime_hardening/overlay/runtime_hardening_overlay.mjs
workspace/runtime_hardening/src/config.mjs
workspace/runtime_hardening/src/index.mjs
workspace/runtime_hardening/src/log.mjs
workspace/runtime_hardening/src/mcp_singleflight.mjs
workspace/runtime_hardening/src/paths.mjs
workspace/runtime_hardening/src/retry_backoff.mjs
workspace/runtime_hardening/src/security/fs_sandbox.mjs
workspace/runtime_hardening/src/security/tool_sanitize.mjs
workspace/runtime_hardening/src/session.mjs
workspace/runtime_hardening/tests/config.test.mjs
workspace/runtime_hardening/tests/fs_sandbox.test.mjs
workspace/runtime_hardening/tests/mcp_singleflight.test.mjs
workspace/runtime_hardening/tests/retry_backoff.test.mjs
workspace/runtime_hardening/tests/session.test.mjs
workspace/runtime_hardening/tests/tool_sanitize.test.mjs
workspace/scripts/rebuild_runtime_openclaw.sh
```

#### B2. Re-run previously failing node groups (requested command form)

```bash
node --test --test-reporter=spec tests/redact_audit_evidence.test.js
node --test --test-reporter=spec tests/secrets_cli_exec.test.js
node --test --test-reporter=spec tests/secrets_cli_plugin.test.js
node --test --test-reporter=spec tests/system2_experiment.test.js
node --test --test-reporter=spec tests/system2_snapshot_diff.test.js
```

```text
✖ tests/redact_audit_evidence.test.js ... EXIT_CODE:1
✖ tests/secrets_cli_exec.test.js ... EXIT_CODE:1
✖ tests/secrets_cli_plugin.test.js ... EXIT_CODE:1
✖ tests/system2_experiment.test.js ... EXIT_CODE:1
✖ tests/system2_snapshot_diff.test.js ... EXIT_CODE:1
```

Detailed direct reruns (same test files via `node <file>`) continue to fail with the same historical assertions:

```text
FAIL CLI redacts synthetic fixtures and writes output bundle: CLI should emit JSON summary
FAIL secrets cli exec injects alias env keys without printing values: expected injected env key summary
FAIL secrets cli status prints enablement header (no secrets): expected /secrets_bridge_enabled=(true|false)/
FAIL no-change fixture yields INCONCLUSIVE: CLI failed (3)
FAIL JSON output is stable and ignores timestamp fields by default: Unexpected end of JSON input
```

#### B3. Trace touch check against hardening paths

```bash
rg -n "workspace/runtime_hardening|rebuild_runtime_openclaw\.sh|\.runtime/openclaw/dist" /tmp/dali_*.out -S || true
```

```text
(no matches)
```

Conclusion: the currently failing groups do not touch hardening module paths or runtime overlay/rebuild paths.

### C) CI / merge-safety adjustment

Added dedicated workflow for first-class hardening gates without weakening existing full-suite checks:

- `.github/workflows/hardening-checks.yml`
  - `npm run typecheck:hardening`
  - `npm run test:hardening`

Existing workflows that run full `npm test` remain unchanged.

## Rollback Plan

1. Revert hardening commits in reverse order:
   - `git revert 1756d03 d504d6e fd46871 9903826 268d4e8`
2. Rebuild runtime without overlay import (or restore prior rebuild script).
3. Re-run baseline test command(s) and confirm clean behavior.

## Known Limitations

- `npm` registry access was unavailable (`EAI_AGAIN`), so external deps (`zod`, `pino`, `vitest`) were not installable.
- Equivalent hardening behavior is implemented with local modules and Node test runner instead of those deps.
- Upstream OpenClaw distributed package does not include original `src/*.ts`; hardening is applied as a runtime overlay layer plus deterministic local modules.
- Full repository test suite (`npm test`) still reports existing unrelated failures in legacy integration/CLI tests; hardening suite is passing and isolated (`npm run test:hardening`).
