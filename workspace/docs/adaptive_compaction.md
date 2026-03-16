# Adaptive Compaction (OpenClaw) — Design + Validation Notes

## What changed

Implemented a least-invasive upgrade in `core/system2/inference/provider_registry.js`:

1. **Compaction timing gates**
   - Added `evaluateCompactionTimingGate(...)` to delay compaction when:
     - multi-step work is active,
     - tool work appears in flight,
     - user intent is still clarifying,
     - plan/state is not externalized,
     - task-adhesion risk is high.

2. **Boundary-moment preference**
   - Gate permits compaction when boundary metadata is present:
     - `task_completed`, `deliverable_sent`, `plan_restated`, `branch_closed`, `context_switch`, or `compaction_boundary_reason`.

3. **Task-adhesion risk score**
   - Added `computeTaskAdhesionRisk(...)` using:
     - unresolved asks,
     - open commitments,
     - pending tools,
     - whether plan/state was externalized.

4. **Checkpoint-before-compaction**
   - Added `buildCompactionCheckpoint(...)` and emits `freecompute_dispatch_compaction_checkpoint` event before compaction.
   - Checkpoint captures:
     - goal, next step, why it matters, success condition,
     - constraints, decisions, tensions,
     - continuity entities/files/projects,
     - open loops.

5. **3-layer prototype**
   - Checkpoint includes:
     - `pinned_core`
     - `active_state`
     - `archive_digest`

6. **Preservation + redundancy strategy**
   - Preserve high-value continuity anchors in checkpoint layers.
   - Continue existing message compaction for redundancy trimming.

## Integration points

- Preflight compaction path now:
  1. evaluates gate,
  2. optionally emits checkpoint,
  3. prepends checkpoint system message,
  4. compacts.

- Error-triggered compaction retry (`400/413` likely context-too-large) follows the same gate + checkpoint flow.

## New events

- `freecompute_dispatch_compaction_gate`
- `freecompute_dispatch_compaction_checkpoint`
- Existing `freecompute_dispatch_compaction_applied` now may include:
  - `checkpoint_included`
  - `task_adhesion_risk`

## Tests added

In `tests/freecompute_cloud.test.js`:

- `registry: compaction gate delays preflight when task adhesion risk is high`
- `registry: boundary moment allows compaction + emits checkpoint layers`

## Tradeoffs

- **Chosen path:** inference-layer compaction gating/checkpoint only (minimal refactor).
- **Not done in this pass:** deep orchestration-state introspection across all runtimes.
- **Reason:** preserve behavior surface while adding policy-aware timing and continuity scaffolding.
