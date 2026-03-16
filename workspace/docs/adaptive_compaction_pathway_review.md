# Adaptive Compaction — Optimal Pathway, Review Criteria, and Integration Map

_Status: architecture note / review rubric. Conservative doc-only follow-up to existing implementation in `core/system2/inference/provider_registry.js` and tests in `tests/freecompute_cloud.test.js`._

## Why this note exists

`workspace/docs/adaptive_compaction.md` records what was already added. This note tightens the next question:

1. what the **best operational pathway** should be,
2. what changes from Codex should be accepted or rejected against,
3. where the existing OpenClaw code/docs can supply better signals.

The current implementation is already useful, but it is still mostly an **inference-layer policy shim**. The main architectural opportunity now is to improve the quality of the metadata supplied into that shim, not to make the compactor itself much more aggressive.

---

## Current state in repo

### Already implemented

In `core/system2/inference/provider_registry.js`:

- `computeTaskAdhesionRisk(messages, metadata)`
- `evaluateCompactionTimingGate({ messages, metadata, trigger })`
- `buildCompactionCheckpoint(messages, metadata, trigger)`
- preflight compaction gating
- error-triggered (`400` / `413`) compaction retry gating
- checkpoint injection as a synthetic system message
- audit events:
  - `freecompute_dispatch_compaction_gate`
  - `freecompute_dispatch_compaction_checkpoint`
  - `freecompute_dispatch_compaction_applied`

In `tests/freecompute_cloud.test.js`:

- under-budget case
- materially-over-budget preflight compaction
- `400` retry compaction
- high task-adhesion delay case
- boundary-moment compaction + checkpoint emission

### Current limits

The implementation mostly relies on:

- message text heuristics,
- caller-supplied `metadata`,
- a synthetic checkpoint packed back into `messages`.

That means the biggest remaining risk is **not bad truncation code**; it is **weak or missing state signals** at dispatch time.

---

## Recommended optimal pathway

This is the preferred compaction sequence for future work.

### Phase 0 — Detect pressure, but do not compact immediately

When request size is nearing or exceeding provider budget:

1. estimate request shape,
2. resolve provider/model budget,
3. classify whether this is:
   - safe preflight compression,
   - a delay-worthy active-work moment,
   - or a hard retry path after provider rejection.

**Principle:** treat compaction as a state transition, not a string-trimming operation.

### Phase 1 — Ask: “is this a boundary moment?”

Compaction should be preferred only when one of these is true:

- task completed,
- deliverable sent,
- explicit plan restated,
- branch/workstream closed,
- context switch initiated,
- caller provides an explicit boundary reason.

If not, compaction should usually be delayed when:

- unresolved asks remain,
- tools are still in flight,
- assistant has made open commitments,
- plan is not yet externalized,
- the user is still clarifying intent.

**Opinion:** this is the right center of gravity. Over-eager compaction during active task adhesion is worse than slightly oversize context.

### Phase 2 — Build checkpoint before any destructive compression

Before trimming messages, emit a checkpoint with three layers:

#### 1. `pinned_core`
Things that must survive compaction because loss causes misalignment, not just inconvenience.

Should include:

- current goal,
- why it matters,
- success condition,
- hard constraints,
- decisions already made,
- tensions/tradeoffs,
- named entities / files / projects.

#### 2. `active_state`
Things needed to resume execution, not just understand history.

Should include:

- next step,
- open loops,
- pending tools,
- unresolved asks,
- whether plan is externalized,
- ideally later: active branch / current artifact / pending verification step.

#### 3. `archive_digest`
Compressed sketch of recent history to preserve local narrative continuity.

Should stay lossy and bounded.

### Phase 3 — Compact toward a target below provider ceiling

The current implementation compacts to ~90% of `maxChars`. That is directionally right.

Recommended rule:

- preflight compaction target: **85–90%** of resolved provider budget,
- retry-after-error target: **80–85%**,
- if still over after checkpoint injection, trim archive layer first, then lower-priority user/assistant history, while preserving `pinned_core` and `active_state`.

### Phase 4 — Emit observability every time

Every compaction decision should remain observable through events.

Minimum event story:

1. gate decision,
2. checkpoint created or skipped,
3. compaction applied or skipped,
4. provider response after compaction,
5. fallback / all-candidates-failed summary if needed.

### Phase 5 — Learn from the result

Longer-term, compaction should not only be policy-driven; it should be outcome-aware.

Useful future metrics:

- did the assistant drop a user ask after compaction?
- did it repeat work already done?
- did it lose tool-state continuity?
- did post-compaction repair messages increase?
- was compaction followed by success, fallback, or failure?

---

## Architectural stance: layered memory should stay logical first, durable second

There are two ways to evolve this:

1. keep layered memory as an **inline checkpoint object** used only during dispatch,
2. promote layered memory into a **durable state surface** shared with orchestration/runtime memory.

Recommended path:

### Near term
Keep the current inline checkpoint path, but make it cleaner and better-fed.

Why:

- minimal behavioral risk,
- no new persistence semantics,
- immediate value,
- easier to test.

### Mid term
Add an optional durable checkpoint sink, but do **not** make dispatch depend on it.

Why:

- dispatch must remain resilient even when external memory/state stores are stale or absent,
- synchronous inference should not block on heavier memory subsystems.

### Long term
Unify compaction checkpoint schema with broader memory/orchestration schemas.

The important design point is:

> `pinned_core`, `active_state`, and `archive_digest` should become a shared conceptual contract, even if different runtimes persist them differently.

---

## What good Codex output should be judged against

Use this as the review rubric.

## A. Timing / gating correctness

Accept changes only if they:

- preserve the idea that active multi-step work should usually block preflight compaction,
- preserve explicit boundary reasons as an override,
- avoid compacting merely because content is large,
- keep error-triggered retry compaction bounded (no retry loops).

Reject or scrutinize changes that:

- compact before checking task adhesion,
- remove boundary-moment semantics,
- make compaction unconditional for size overflow,
- add repeated compaction retries across multiple candidates without hard caps.

## B. Checkpoint quality

Accept changes only if checkpoints remain execution-useful.

A good checkpoint should let a fresh model answer:

- What are we doing?
- What matters about it?
- What is the next step?
- What is still unresolved?
- What constraints or decisions must not be violated?

Reject or scrutinize changes that:

- turn checkpoint content into vague summaries,
- drop active-state fields,
- overfit to transcript prose without capturing operational state,
- bloat checkpoint size so much that it consumes the compaction savings.

## C. Layer priority discipline

Accept changes only if they keep a clear hierarchy:

1. preserve `pinned_core`,
2. preserve `active_state`,
3. trim `archive_digest` first,
4. trim lower-value transcript redundancy after that.

Reject changes that flatten all layers into one blob and then truncate indiscriminately.

## D. Observability / auditability

Accept changes only if operators can still answer:

- why compaction happened or did not happen,
- what provider/model budget was involved,
- whether checkpoint was included,
- what trigger fired (`preflight`, `error_400`, `error_413`),
- whether the result improved or still failed.

Reject changes that reduce emitted evidence or hide compaction cause.

## E. Safety / boundedness

Accept changes only if they are bounded by:

- one size-retry per provider attempt,
- finite checkpoint size,
- finite archive size,
- deterministic fallback behavior.

Reject changes that risk:

- unbounded retries,
- recursive checkpoint nesting,
- dependence on network/durable stores inside dispatch hot path,
- mutation of caller env/state in order to compact.

## F. Metadata realism

This is the biggest one.

Accept changes that improve how `metadata` is sourced from real runtime state.

Reject changes that just add more heuristics inside `provider_registry.js` without improving upstream signal quality.

My view: the registry is already doing enough inference. The next win is better inputs, not cleverer guessing.

---

## Best next integration points in existing code/docs

These are the highest-value places to connect into the current compaction system.

## 1. `workspace/scripts/message_handler.py`

Why it matters:

- it already constructs conversation context,
- it likely has the closest visibility into recent user asks and summary boundaries,
- it is a natural place to derive:
  - `unresolved_asks`
  - `intent_clarifying`
  - `context_switch`
  - `deliverable_sent`

Best use:

- compute lightweight dispatch metadata before handing off to inference,
- do not move compaction logic here; only enrich metadata.

## 2. Team chat / planner state surfaces

Files worth reviewing as metadata suppliers:

- `workspace/scripts/team_chat.py`
- `workspace/scripts/team_chat_adapters.py`
- `workspace/memory/session_handshake.py`
- `workspace/memory/relationship_tracker.py`

Why they matter:

- they already encode plan summaries, session state, and boundaries,
- they are strong candidates for:
  - `plan_externalized`
  - `plan_restated`
  - `multi_step_active`
  - `branch_closed`
  - `open_commitments`

Best use:

- produce normalized dispatch metadata from planner/session state instead of re-deriving everything from message text.

## 3. `workspace/memory/context_compactor.py`

Why it matters:

- despite being a much simpler legacy compactor, it is the obvious conceptual sibling.

Best use:

- do **not** merge logic blindly,
- do document the distinction between:
  - legacy generic context compaction, and
  - provider-budget-aware dispatch compaction.

If later unified, the schema/layer concepts should be shared first, not the truncation algorithm.

## 4. `docs/system1/ROUTING_POLICY.md`

Why it matters:

- routing docs already explain provider selection,
- compaction is now effectively part of provider compatibility behavior.

Best use:

- add a short section later describing provider-budget-aware compaction behavior and emitted events.

## 5. `tests/freecompute_cloud.test.js`

Why it matters:

- this is the living contract today.

Best use:

Add the next tests here before larger refactors:

- boundary reason precedence over high risk,
- archive-first trimming behavior,
- checkpoint-size cap,
- no recursive checkpointing on already-compacted payloads,
- metadata alias parity (`pendingTools`, `planExternalized`, etc.),
- multi-provider fallback after compaction still preserves checkpoint observability.

---

## Concrete gaps still open

## Gap 1 — dispatch metadata is under-specified

The registry supports useful keys, but there is not yet a visible repo-wide contract for who sets them and when.

Recommended next step:

- create a tiny schema/doc for dispatch metadata fields,
- keep it near inference docs or next to the registry.

Suggested fields:

- `current_goal`
- `next_step`
- `success_condition`
- `constraints[]`
- `open_loops[]`
- `unresolved_asks`
- `open_commitments`
- `pending_tools`
- `plan_externalized`
- `multi_step_active`
- `tools_in_flight`
- `intent_clarifying`
- `task_completed`
- `deliverable_sent`
- `plan_restated`
- `branch_closed`
- `context_switch`
- `compaction_boundary_reason`

## Gap 2 — no explicit checkpoint size budget

The checkpoint is helpful, but it currently rides inside a synthetic system message and can itself become large.

Recommended next step:

- cap each layer independently,
- cap serialized checkpoint size before insertion,
- prefer trimming `archive_digest` first.

Status update:

- `core/system2/inference/provider_registry.js` now has explicit checkpoint byte caps before insertion.
- The current remaining gap is less about raw size safety and more about upstream metadata quality / producer coverage.

## Gap 3 — no durable handoff between orchestration state and compaction state

The checkpoint knows just enough to preserve continuity in one call, but not enough to become a cross-runtime state primitive.

Recommended next step:

- define a shared logical schema before any persistence work.

## Gap 4 — no post-compaction quality checks

We know compaction happened, but not whether it harmed task completion.

Recommended next step:

- record lightweight follow-up audit markers for dropped-ask / repeated-work / fallback-after-compaction cases.

---

## Recommended next safe implementation slice

If Codex is asked to continue this work, the safest high-value slice is:

1. add a small documented metadata contract for dispatch callers,
2. add checkpoint/layer byte caps,
3. add tests for archive-first trimming and checkpoint cap behavior,
4. add one upstream metadata integration point in the main message handling path.

That would improve the architecture materially without forcing a large runtime refactor.

---

## Bottom line

The current implementation has the right instinct:

- delay compaction during active adhesion,
- prefer boundary moments,
- checkpoint before compression,
- preserve layered continuity.

The next frontier is **state quality**, not more aggressive compression.

If future Codex output tries to get clever mainly by truncating harder or summarizing more, be skeptical.
If it improves the metadata contract, layer budgets, and test coverage while keeping compaction bounded and observable, that is probably the right move.
