# Chain Runner

## Overview
Deterministic, token-budgeted sub-agent chain for OpenClaw. It decomposes requests into tasks, routes them to model profiles, enforces budget ceilings, and writes append-only traces.

## Run
```bash
node scripts/run_chain.js "draft a codex prompt for X"
```

Environment overrides:
- `CHAIN_TOKEN_CEILING` (default 6000)
- `CHAIN_STEP_TOKEN_CEILING` (default 2000)
- `CHAIN_LATENCY_CEILING_MS` (default 30000)

## Trace Logs
- File: `logs/chain_runs/chain_trace.jsonl`
- Each line: JSON object with runId, step, modelProfile, token estimates, duration, outcome, summary.

## Profiles
- `cheap_transform`: local-first when `OPENCLAW_LOCAL_FALLBACK=1`, otherwise remote.
- `reasoning_remote`: remote reasoning steps.
- `code_remote`: remote code steps.

## Budgeting
- Token estimate: `chars/4` with safety margin.
- Budget enforcement pins invariants and truncation note; prunes scratch, artifacts, then rolling summary.

## Failure Behavior
If budget cannot be recovered, chain aborts with `CHAIN_BUDGET_EXCEEDED`. Trace entries capture the last successful step.
