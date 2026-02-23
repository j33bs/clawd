# Φ Proxy Session v7 (Propagation Links, Not IIT Φ)

Date (UTC): 2026-02-23T11:48:59Z
Baseline commit before v7 intervention: f7e6a84
Input artifact: `workspace/governance/OPEN_QUESTIONS.md`

## Purpose

Add minimal binding links from non-Governance sections to the Micro-Governance Hub, then rerun the same v4/v5/v6 constraint-influence measurement to test whether dependence on Governance decreases.

## BEFORE (v6 baseline)

| Variant | decisions | constraints | avg_constraints | unique_constraints |
|---|---:|---:|---:|---:|
| v6 Full | 23 | 30 | 1.304348 | 8 |
| v6 CutA (Governance removed) | 11 | 15 | 1.363636 | 6 |

v6 gap baseline:

- Decisions gap (Full-CutA): 12
- Unique-constraints gap (Full-CutA): 2

## Intervention (append-only)

Added exactly three non-Governance binding-link lines (outside Governance & Alignment):

1. `Binding link: this TACTI-facing section participates in the rules of the ‘✦ Micro-Governance Hub (Added 2026-02-24)’ and will log probe outcomes.`
2. `Binding link: this identity thread participates in the rules of the ‘✦ Micro-Governance Hub (Added 2026-02-24)’.`
3. `Binding link: this process thread participates in the rules of the ‘✦ Micro-Governance Hub (Added 2026-02-24)’.`

## Method (unchanged)

Same v4 heuristic set:

- Decision-like lines detected via tokens: `{ must, should, will, commit, decide, require, enforce, verify, log, measure, update, merge, run, add, remove }`
- Constraint counting via operator set: `{ must, should, shall, will, commit, verify, audit, enforce, require, forbid, rule, constraint, obligation, responsibility, decide, measure, log, append }`
- Metrics for Full and CutA:
  - decisions
  - constraints
  - avg_constraints
  - unique_constraints

## AFTER (v7)

| Variant | decisions | constraints | avg_constraints | unique_constraints |
|---|---:|---:|---:|---:|
| v7 Full | 24 | 32 | 1.333333 | 8 |
| v7 CutA | 12 | 17 | 1.416667 | 7 |

## Deltas (v7 vs v6)

| Comparison | Δdecisions | Δconstraints | Δavg_constraints | Δunique_constraints |
|---|---:|---:|---:|---:|
| v7 Full - v6 Full | +1 | +2 | +0.028985 | +0 |
| v7 CutA - v6 CutA | +1 | +2 | +0.053031 | +1 |

Gap movement:

- Decisions gap (Full-CutA): `12 -> 12` (no shrink)
- Unique-constraints gap (Full-CutA): `2 -> 1` (shrank by 1)

## Interpretation Rule

- Strong positive: CutA decisions increase and decision-gap shrinks.
- Moderate positive: CutA decisions increase but decision-gap unchanged.
- Supporting signal: CutA unique constraints increase and/or unique-gap shrinks.
- Always proxy-only: not IIT Φ, not consciousness evidence.

## Interpretation

Moderate positive with supporting signal.

- CutA decisions increased (`11 -> 12`) but decision-gap did not shrink.
- CutA unique constraints increased (`6 -> 7`) and unique-gap narrowed (`2 -> 1`).
- This indicates propagation of some constraint vocabulary into non-Governance regions, while decision-count centralization remains stable.

This remains a bounded structural probe, not Φ.
