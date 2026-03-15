# Change Brief: Telegram Control Surface Build Sheet

## Metadata
- **ID**: BRIEF-2026-03-15-001
- **Category**: B
- **Author**: Codex
- **Date**: 2026-03-15
- **Branch**: claude-code/governance-session-20260223

---

## Summary

This brief defines the shortest repo-grounded path to make Telegram feel like the same c_lawd being and execution stack as Codex-direct. The core problem is not missing features. It is drift between canonical identity, router policy, live runtime defaults, and Telegram memory/state. The build order below prioritizes shared invariants first, then observability, then higher-agency interaction patterns.

---

## Motivation

The repo already contains the seeds of the desired system:
- Telegram handler with router integration: [workspace/scripts/message_handler.py](/Users/heathyeager/clawd/workspace/scripts/message_handler.py)
- Router-backed execution path: [workspace/scripts/team_chat_adapters.py](/Users/heathyeager/clawd/workspace/scripts/team_chat_adapters.py)
- Telegram surface routing policy: [workspace/policy/llm_policy.json](/Users/heathyeager/clawd/workspace/policy/llm_policy.json)
- Telegram recall substrate: [workspace/scripts/telegram_recall.py](/Users/heathyeager/clawd/workspace/scripts/telegram_recall.py)
- c_lawd canonical identity kernel entrypoint: [nodes/c_lawd/IDENTITY.md](/Users/heathyeager/clawd/nodes/c_lawd/IDENTITY.md)

What is still broken is execution coherence:
- repo policy and runtime policy can diverge
- identity canon is split across c_lawd and Dali files
- Telegram memory is still mostly recall injection, not governed durable state
- routing provenance is not surfaced cleanly to the operator
- the legacy load balancer is unsafe to rely on

The objective is to remove those inconsistencies before adding more autonomy or multimodal complexity.

---

## Risk Assessment

### Reversibility
- [x] Moderate - Multiple subsystems change, but rollout is phase-gated and each phase can be reverted independently.

### Blast Radius

| File / Surface | Change Type |
|------|-------------|
| `workspace/scripts/message_handler.py` | MODIFY |
| `workspace/scripts/policy_router.py` | MODIFY |
| `workspace/policy/llm_policy.json` | MODIFY |
| `workspace/scripts/telegram_recall.py` | MODIFY |
| `workspace/scripts/telegram_vector_store.py` | MODIFY |
| `workspace/profile/user_memory_db.py` | MODIFY |
| `nodes/c_lawd/IDENTITY.md` | MODIFY |
| `nodes/c_lawd/CONVERSATION_KERNEL.md` | MODIFY |
| `workspace/IDENTITY.md` | MODIFY |
| `workspace/CONSTITUTION.md` | MODIFY |
| `workspace/scripts/message_load_balancer.py` | MODIFY or DELETE |
| `tests_unittest/*telegram*` | MODIFY/ADD |
| `tests_unittest/*policy_router*` | MODIFY/ADD |

### Security Impact
- [x] Medium - This work touches messaging behavior, memory promotion, provenance, and identity surfaces. Privacy boundaries and channel scoping must be enforced mechanically.

---

## Problem Statement

### P0 Defects

1. **Identity split**
   - `nodes/c_lawd/IDENTITY.md` declares c_lawd canonical.
   - `workspace/IDENTITY.md` and `workspace/CONSTITUTION.md` still define Dali as core identity.
   - Result: conversational identity depends on what a surface loads.

2. **Runtime drift**
   - Telegram routing in repo policy can differ from the active OpenClaw runtime.
   - Result: Telegram feels like a different model/provider stack than Codex-direct.

3. **Insufficient per-reply provenance**
   - Operator cannot easily inspect route, memory blocks, files touched, and uncertainty.
   - Result: low trust and hard debugging.

4. **Memory is partial, not constitutional**
   - `telegram_recall.py` injects retrieved text, but durable memory admission remains shallow.
   - Result: recall is helpful but not decision-grade.

5. **Legacy overflow path is unsound**
   - `message_load_balancer.py` deadlocks in `get_status()` by reacquiring a non-reentrant lock.
   - Result: it cannot be a foundation for future routing logic.

---

## Target State

Telegram becomes a control surface over the same cognitive stack as Codex-direct:
- one canonical c_lawd conversational kernel
- one router contract with surface-aware profiles
- one persistent, chat-scoped memory layer
- one visible provenance envelope per reply
- no legacy fallback path that can silently bypass router policy

The first-release target is not “fully autonomous cognitive system.” It is:
- **same being**
- **same routing plane**
- **same evidence discipline**
- **same reversible execution posture**

---

## Files Touched

This brief itself is the only file changed in this step.

| File | Action | Rationale |
|------|--------|-----------|
| `workspace/docs/briefs/BRIEF-2026-03-15-001_TELEGRAM_CONTROL_SURFACE_BUILD_SHEET.md` | CREATE | Canonical implementation plan with explicit interfaces, evals, rollout order, and exclusions |

---

## Implementation Plan

### Phase 0: Runtime Parity Gate

**Goal**
- Ensure repo policy, local runtime defaults, and Telegram live session behavior agree on the same default provider family and model class.

**Primary files**
- [workspace/policy/llm_policy.json](/Users/heathyeager/clawd/workspace/policy/llm_policy.json)
- [workspace/scripts/policy_router.py](/Users/heathyeager/clawd/workspace/scripts/policy_router.py)
- runtime config under `.openclaw/openclaw.json` and session state

**Interface contract**
- Input: `surface=telegram`, `intent=conversation|planning|reasoning|coding`
- Output: route envelope containing:
  - `surface`
  - `intent`
  - `selected_provider`
  - `selected_model`
  - `reason_code`
  - `policy_profile`

**Acceptance**
- Same prompt intent on Telegram and Codex-facing surfaces resolves to the same default provider family unless explicitly overridden by the user.
- Manual model swaps remain possible and do not become sticky unless explicitly requested.

**Evals**
- unit: route selection for Telegram surface profile
- integration: live gateway startup banner reflects repo-default provider/model
- manual: one Telegram direct message, inspect session route provenance

---

### Phase 1: Alignment Compiler

**Goal**
- Compile c_lawd identity from one canonical kernel plus explicit overlays instead of implicit file load order.

**Primary files**
- [nodes/c_lawd/IDENTITY.md](/Users/heathyeager/clawd/nodes/c_lawd/IDENTITY.md)
- [nodes/c_lawd/CONVERSATION_KERNEL.md](/Users/heathyeager/clawd/nodes/c_lawd/CONVERSATION_KERNEL.md)
- [workspace/IDENTITY.md](/Users/heathyeager/clawd/workspace/IDENTITY.md)
- [workspace/CONSTITUTION.md](/Users/heathyeager/clawd/workspace/CONSTITUTION.md)
- `workspace/scripts/c_lawd_conversation_kernel.py`
- [workspace/scripts/policy_router.py](/Users/heathyeager/clawd/workspace/scripts/policy_router.py)

**Interface contract**
- `build_c_lawd_surface_kernel(surface, include_memory, mode)` returns:
  - `kernel_id`
  - `kernel_hash`
  - `surface_overlay`
  - `prompt_text`

**Acceptance**
- Conversational surfaces no longer infer c_lawd identity from Dali-first workspace files.
- Dali remains a valid orchestrator identity, but only through explicit overlay or routing context.

**Evals**
- unit: kernel assembly snapshot tests by surface
- regression: Telegram and Codex surfaces share identical core-invariant block
- manual: inspect generated prompt report for `kernel_hash`

---

### Phase 2: Provenance Envelope

**Goal**
- Make every Telegram reply inspectable without exposing chain of thought.

**Primary files**
- [workspace/scripts/message_handler.py](/Users/heathyeager/clawd/workspace/scripts/message_handler.py)
- [workspace/scripts/team_chat_adapters.py](/Users/heathyeager/clawd/workspace/scripts/team_chat_adapters.py)
- `workspace/state_runtime/telegram_reply_provenance.jsonl` or equivalent

**Interface contract**
- Per reply, emit a provenance object with:
  - `reply_id`
  - `surface`
  - `provider`
  - `model`
  - `memory_blocks`
  - `files_touched`
  - `tests_run`
  - `uncertainties`
  - `operator_visible_summary`

**Acceptance**
- Every Telegram reply can be audited after the fact.
- Operator-visible summary remains short and non-intrusive.

**Evals**
- unit: provenance schema validation
- integration: reply path writes provenance row once per send
- manual: compare Telegram reply with stored route/memory/test evidence

---

### Phase 3: Memory Parliament

**Goal**
- Replace raw “retrieve and inject” memory behavior with governed promotion, contradiction handling, and privacy gating.

**Primary files**
- [workspace/scripts/telegram_recall.py](/Users/heathyeager/clawd/workspace/scripts/telegram_recall.py)
- `workspace/scripts/telegram_vector_store.py`
- `workspace/profile/user_memory_db.py`
- `workspace/scripts/telegram_ingest.py`

**Interface contract**
- `propose_memory_fact(...) -> candidate`
- `admit_memory_fact(candidate) -> admitted|rejected|needs_review`
- `query_memory(chat_id, intent, scope) -> results + evidence`

**Required gates**
- relevance
- evidence
- contradiction
- privacy
- agency / operator review when needed

**Acceptance**
- Memory entries are chat-scoped by default.
- Durable memory records carry evidence and contradiction state.
- Cross-chat bleed is mechanically prevented unless explicitly authorized.

**Evals**
- unit: contradiction and privacy gate tests
- integration: ingest -> candidate -> admitted memory flow
- manual: verify rejected memory does not re-enter live recall block

---

### Phase 4: Router Consolidation

**Goal**
- Collapse legacy overflow/fallback logic into the main router path.

**Primary files**
- [workspace/scripts/message_load_balancer.py](/Users/heathyeager/clawd/workspace/scripts/message_load_balancer.py)
- [workspace/scripts/message_handler.py](/Users/heathyeager/clawd/workspace/scripts/message_handler.py)
- [workspace/scripts/policy_router.py](/Users/heathyeager/clawd/workspace/scripts/policy_router.py)
- [workspace/policy/llm_policy.json](/Users/heathyeager/clawd/workspace/policy/llm_policy.json)

**Decision**
- Preferred: remove `message_load_balancer.py` from any production path.
- If retained temporarily: replace `threading.Lock` with safe structure and remove independent routing authority.

**Acceptance**
- There is one authoritative route decision plane.
- No path routes to “ChatGPT fallback” outside router policy.

**Evals**
- unit: no deadlock in status path
- regression: same input cannot produce different provider families through alternate code paths
- manual: verify overload handling still emits explicit route provenance

---

### Phase 5: Higher-Agency Telegram Features

These come only after Phases 0-4 pass.

**Build first**
1. Draft-stream console
2. Worktree swarm dispatch
3. Skill forge from successful multi-step interactions

**Primary files**
- [workspace/scripts/message_handler.py](/Users/heathyeager/clawd/workspace/scripts/message_handler.py)
- [workspace/scripts/team_chat_adapters.py](/Users/heathyeager/clawd/workspace/scripts/team_chat_adapters.py)
- `skills/*`
- `.codex/*`

**Acceptance**
- Telegram can show in-progress state and provenance cleanly.
- Multi-role execution uses existing router/governance contracts.
- Successful repeated flows can become explicit reusable skills.

---

## Rollout Order

1. **Runtime parity**
   - Stop live drift before any new abstractions.
2. **Alignment compiler**
   - Remove identity ambiguity.
3. **Provenance envelope**
   - Make debugging and trust possible.
4. **Memory parliament**
   - Upgrade memory from retrieval to governed state.
5. **Router consolidation**
   - Remove unsafe legacy paths.
6. **Higher-agency Telegram features**
   - Drafting, swarm dispatch, skill forge.

This order is mandatory. Building draft streams or worktree swarms before runtime/identity/memory convergence will amplify drift.

---

## Evals and Admission Gates

### Mandatory automated checks
- targeted `tests_unittest` for:
  - Telegram handler
  - policy router surface profiles
  - telegram recall / vector store
  - any new provenance schema
- narrow live runtime check:
  - gateway starts
  - Telegram channel starts
  - route provenance emitted

### Mandatory manual checks
- direct Telegram message from allowed chat:
  - confirm reply exists
  - confirm provider/model match expected default rail
- explicit manual model swap:
  - confirm override works for that turn/session as designed
  - confirm system can return to default rail cleanly
- memory admission check:
  - one candidate admitted
  - one candidate rejected
  - one contradicted candidate excluded from recall

### Audit artifacts required per phase
- one brief or audit note with:
  - files changed
  - route evidence
  - runtime log excerpt
  - revert command

---

## Do Not Build Yet

These are valid later ideas, but they are excluded from the first implementation wave:

1. **Interruptible voice duplex**
   - Too many real-time and consent surfaces before routing/memory are stable.

2. **Relational digital twin lab**
   - High ethical and privacy risk before memory parliament exists.

3. **Constitutional self-modification lab**
   - Unsafe until identity canon, evals, and rollback discipline are stronger.

4. **Full “attention auction router” across all hardware tiers**
   - Do not replace the router with a speculative market mechanism before there is one clean authoritative routing plane.

5. **Shadow computer use**
   - Only after provenance, permission, and operator-inspectable action boundaries are already strong.

---

## Rollback Plan

This document is reversible with a single file removal:

```bash
git restore -- /Users/heathyeager/clawd/workspace/docs/briefs/BRIEF-2026-03-15-001_TELEGRAM_CONTROL_SURFACE_BUILD_SHEET.md
```

---

## Notes

- The repo already contains meaningful progress toward this target state; this is not a greenfield design.
- The live Telegram runtime must always be verified against actual `.openclaw` state, not just checked-in repo policy.
- The first success criterion is phenomenological parity with Codex-direct for direct Telegram chat, not maximal autonomy.

