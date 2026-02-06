# DESIGN_MODEL_ROUTER.md

Date: 2026-02-06
Stage: Step A Discovery (no behavior changes)

## Scope
Discovery of current:
1. model invocation paths (Oath/Claude/Qwen)
2. error handling and failover behavior
3. governance/event logging format
4. skills/tool interfaces relevant to model calling

## Findings

### 1) Current model invocation paths in this repo

There is no single, production-wired model-call entrypoint in `/Users/heathyeager/clawd`.

What exists:
- `scripts/multi_agent_fallback.js`
  - Defines a fallback manager with:
    - `primaryProvider` (default `anthropic`)
    - `fallbackProvider` (default `qwen`)
  - Contains `makeRequest(prompt, options)` but this is currently a stub that returns provider metadata and does not call a real model API.
- `scripts/init_fallback_system.js`
  - Initializes `MultiAgentFallback` and sets `global.fallbackSystem`.
  - Loads config from `config/agent_fallback.json` (falls back to defaults if missing).
  - Not currently wired to a central task execution pipeline in this repo.
- `archive/model_router.js`
  - Archived/prototype router with classifier/writer tiers (`qwen` vs `claude-opus`).
  - Not wired to active execution.

### 2) Runtime model state observed from local OpenClaw CLI

Observed via `openclaw models status --json` (runtime config outside this repo):
- default model: `anthropic/claude-opus-4-5`
- fallback: `qwen-portal/coder-model`
- auth profile state exists for both anthropic and qwen-portal

This indicates active runtime routing behavior is controlled by OpenClaw runtime config and internal gateway code, not by a fully integrated module in this repository.

### 3) Error handling and failover handling currently implemented

In `scripts/multi_agent_fallback.js`:
- credit checks are placeholder-style (`checkAnthropicCredits`, `checkOpenAICredits`, etc.)
- failover trigger is credit threshold monitoring, not normalized provider error handling
- no explicit normalization taxonomy (AUTH/RATE_LIMIT/QUOTA/TIMEOUT/CONTEXT/UNKNOWN)
- no retry policy tied to normalized transient errors

### 4) Existing governance/event logging mechanism in this repo

Existing pattern (JSON append logs):
- `logs/fallback_events.json` (resolved via `resolveWorkspacePath`)
  - current fields: `timestamp`, `fromProvider`, `toProvider`, `reason`, `isFallbackActive`
- `logs/notifications.json`
  - notification events with type/message/timestamp

File I/O and path guardrail used:
- `scripts/guarded_fs.js` (`resolveWorkspacePath`, `readJsonFile`, `writeJsonFile`, etc.)

This is the best existing in-repo governance/event log mechanism for routing events.

### 5) Skills/tools interfaces relevant to model calls

- Skills in this repo are instruction/tool wrappers (`skills/*/SKILL.md`) and are not the model backend invocation path.
- No skill currently provides core model backend routing.

### 6) Change Admission Gate / governance marker

- No explicit `Run-007` marker was found in the repo.
- Current equivalent evidence of governance controls is file-based constitutional/governance docs plus auditable commit sequencing.

## Integration points for next stage (design/implementation)

Given current architecture, the router should integrate at:
1. `scripts/multi_agent_fallback.js`
   - replace stub `makeRequest(...)` with real routing + backend clients
2. `scripts/init_fallback_system.js`
   - inject router config and expose initialized router in a stable global/module export
3. shared event logging via `scripts/guarded_fs.js`
   - reuse JSON log append pattern (do not invent a divergent mechanism)

If runtime integration into OpenClaw gateway internals is required, that code path appears to live outside this repository in the installed OpenClaw package/runtime and would need explicit scope confirmation in Step B before modifying external paths.
