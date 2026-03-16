# c_lawd Weekly Reflection Loop

## Purpose

Distill what should survive the week without forcing raw daily notes to carry long-term continuity by themselves.

This loop exists to improve:
- memory compaction quality,
- pinned-state quality before context loss,
- cross-session recall of active doctrine, commitments, and regressions.

## Cadence

Run once per week, ideally against the last 7 daily notes plus any new canonical artifacts touched that week.

## Inputs

- `memory/YYYY-MM-DD.md` for the covered week
- `MEMORY.md`
- newly created or updated doctrine artifacts under `workspace/docs/source_artifacts/`
- any active operational blockers that kept recurring across sessions

## Output artifact shape

```yaml
period: 2026-WNN
wins:
  - durable improvement with evidence
regressions:
  - what drifted or broke, with evidence
open_loops:
  - active commitments or blockers still live
promotions:
  - items that should move into MEMORY.md or doctrine
retirements:
  - stale items safe to remove or down-rank
pinned_state:
  doctrine:
    - rules that must survive compaction
  commitments:
    - open promises / active constraints
  preferences:
    - user or system defaults still in force
  blockers:
    - recurring operational blockers worth front-loading
receipts:
  - paths, tests, traces, or task ids
```

## Promotion rules

Promote into `MEMORY.md` only when an item changes future behavior across sessions.

Typical promotions:
- stable user preferences,
- repeated operational blockers,
- durable project state changes,
- doctrine updates that multiple surfaces should honor.

Do **not** promote:
- one-off chatter,
- stale experiments with no follow-through,
- speculative interpretations without a path, receipt, or repeated recurrence.

## Reflection questions

1. What kept coming back across sessions?
2. What would have been painful to lose to compaction?
3. Which items are still live enough to belong in pinned state?
4. Which parts of `MEMORY.md` are now stale, duplicated, or too narrativized?
5. What evidence upgrades are needed so future recall is less reconstructive?

## Minimal weekly deliverables

1. One compact weekly summary block.
2. Any necessary `MEMORY.md` promotion or pruning.
3. A pinned-state shortlist with no more than:
   - 5 doctrine items
   - 5 live commitments/blockers
   - 5 active preferences
4. Explicit receipts for every promoted item.

## Acceptance

The loop is successful when a fresh session can recover:
- what still matters,
- what changed this week,
- what must not be dropped during compaction,
- and what next work is still genuinely live.
