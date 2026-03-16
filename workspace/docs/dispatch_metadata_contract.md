# Dispatch Metadata Contract

_Status: near-term contract for inference callers feeding provider dispatch and adaptive compaction._

This document defines the smallest useful metadata surface that upstream callers should populate before calling `ProviderRegistry.dispatch(...)`.

## Purpose

The adaptive compaction path is now mostly policy-correct. The remaining architecture bottleneck is signal quality: if dispatch receives weak state, compaction falls back to transcript heuristics.

This contract keeps the dispatch layer logical and cheap while improving:

- compaction timing quality,
- checkpoint fidelity,
- auditability of why compaction fired or was delayed.

## Field groups

### 1. Task identity

These improve `pinned_core` quality.

- `current_goal: string`
  - Best current statement of what the system is trying to achieve.
- `success_condition: string`
  - Concrete done-state for the active user ask.
- `constraints: string[]`
  - Hard constraints, prohibitions, deadlines, or scope limits.

### 2. Execution state

These improve `active_state` quality.

- `next_step: string`
  - Next concrete action if execution resumes after compaction.
- `open_loops: string[]`
  - Unresolved subthreads, pending confirmations, or blocked follow-ups.
- `pending_tools: number`
  - Count of tool operations still in flight.
- `unresolved_asks: number`
  - Count of active user asks not yet satisfied.
- `open_commitments: number`
  - Count of assistant commitments still outstanding.
- `plan_externalized: boolean`
  - Whether the execution plan has been made explicit in the transcript or metadata.

### 3. Timing / gate hints

These directly affect compaction gating.

- `multi_step_active: boolean`
- `tools_in_flight: boolean`
- `intent_clarifying: boolean`

### 4. Boundary signals

These authorize compaction at natural transition points.

- `task_completed: boolean`
- `deliverable_sent: boolean`
- `plan_restated: boolean`
- `branch_closed: boolean`
- `context_switch: boolean`
- `compaction_boundary_reason: string`

## Minimal producer guidance

Upstream callers do **not** need perfect truth. They should provide the cheapest reliable facts already available from orchestration state.

Priority order:

1. planner/session state,
2. tool runtime state,
3. explicit orchestration markers,
4. transcript heuristics only as fallback.

## Recommended smallest upstream slice

The safest near-term producer is the main message handling path:

1. set `current_goal` from the active request envelope,
2. set `next_step` from planner or most recent intended action,
3. set `pending_tools` / `tools_in_flight` from tool runtime state,
4. set `unresolved_asks` and `open_commitments` from maintained counters,
5. set boundary fields only from explicit orchestration events.

## Non-goals

- Do not make dispatch depend on durable memory.
- Do not block inference on slow state stores.
- Do not encode large transcript summaries into metadata.

## Checkpoint budget notes

`provider_registry.js` now enforces explicit checkpoint byte caps before checkpoint insertion. Upstream metadata should therefore prefer concise, high-signal fields over verbose prose.

## Acceptance criteria for new metadata producers

A new producer is good enough if it makes these questions easier to answer after compaction:

- What are we doing?
- What matters about it?
- What is the next step?
- What is still unresolved?
- Why was compaction allowed or delayed?
