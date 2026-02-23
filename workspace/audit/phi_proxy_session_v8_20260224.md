# Φ Proxy Session v8 (Decision Compiler Replication, Not IIT Φ)

Date (UTC): 2026-02-23T11:58:05Z
Baseline commit before v8 intervention: ebbc1bb
Input artifact: `workspace/governance/OPEN_QUESTIONS.md`

## Purpose

Introduce one minimal decision-compiler micro-ritual outside Governance, then rerun the same v4 influence measurement to test whether decision production decentralizes.

## BEFORE (v7 baseline)

| Variant | decisions | constraints | avg_constraints | unique_constraints |
|---|---:|---:|---:|---:|
| v7 Full | 24 | 32 | 1.333333 | 8 |
| v7 CutA (Governance removed) | 12 | 17 | 1.416667 | 7 |

v7 gap baseline:

- Decisions gap (Full-CutA): 12
- Unique-constraints gap (Full-CutA): 1

## Intervention (verbatim)

```md
## ✦ Decision Micro-Ritual (Added 2026-02-24)

When pressure rises, run this tiny compiler:
1. Select: choose one live question from the Instrumentation Index.
2. Decide: mark it EXPERIMENT PENDING, GOVERNANCE RULE CANDIDATE, or PHILOSOPHICAL ONLY.
3. Log: record the outcome and date in the Index or a linked audit note.

We will verify that each pass names one concrete next move.
This ritual must update either the Result field or an audit link before the next cycle closes.
Outcomes produced here bind subsequent handling of that question.
If a decision cannot be tested, mark it PHILOSOPHICAL ONLY instead of pretending.
This does not replace Governance & Alignment; it is a local decision compiler.
```

## Method (unchanged from v4-v7)

- Decision-like line tokens: `{ must, should, will, commit, decide, require, enforce, verify, log, measure, update, merge, run, add, remove }`
- Constraint operator set: `{ must, should, shall, will, commit, verify, audit, enforce, require, forbid, rule, constraint, obligation, responsibility, decide, measure, log, append }`
- Metrics for Full and CutA:
  - decisions
  - constraints
  - avg_constraints
  - unique_constraints

## AFTER (v8)

| Variant | decisions | constraints | avg_constraints | unique_constraints |
|---|---:|---:|---:|---:|
| v8 Full | 29 | 40 | 1.379310 | 10 |
| v8 CutA | 17 | 25 | 1.470588 | 9 |

## Deltas (v8 vs v7)

| Comparison | Δdecisions | Δconstraints | Δavg_constraints | Δunique_constraints |
|---|---:|---:|---:|---:|
| v8 Full - v7 Full | +5 | +8 | +0.045977 | +2 |
| v8 CutA - v7 CutA | +5 | +8 | +0.053921 | +2 |

Gap movement:

- Decisions gap (Full-CutA): `12 -> 12` (no shrink)
- Unique-constraints gap (Full-CutA): `1 -> 1` (no shrink)

## Interpretation Rule

- Strong positive: CutA decisions increase and decision-gap shrinks.
- Moderate positive: CutA decisions increase but decision-gap unchanged.
- Negative: no meaningful change.
- Always proxy-only: not IIT Φ, not consciousness evidence.

## Interpretation

Moderate positive only.

- CutA decisions increased (`12 -> 17`) and CutA unique constraints increased (`7 -> 9`).
- However, Full and CutA increased in parallel, so the decision gap did not shrink (`12 -> 12`).
- This suggests stronger non-Governance output without reduced centralization under this metric.

This remains a bounded structural probe, not Φ.
