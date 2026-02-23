# Φ Proxy Session v5 (Perturbation: Normative Load Redistribution, Not IIT Φ)

Date (UTC): 2026-02-23T11:35:11Z
Baseline commit before v5 perturbation: 0491c6c
Input artifact: `workspace/governance/OPEN_QUESTIONS.md`

## Purpose

Run a minimal perturbation experiment: append 3–5 tiny obligation carriers in non-Governance sections, rerun the same v4 constraint-influence measurement, and compare before/after.

This is a structural stress test of normative load distribution. It is not IIT Φ.

## Session Definition

- Partition used by v4 (unchanged):
  - A) Governance & Alignment section(s)
  - B) Rest of document
- v5 perturbation applied append-only in non-Governance sections (`## XXXIV` subsections):
  - Added four `Operational note:` lines under:
    - `On what changed in practice`
    - `On Φ, again`
    - `On the character of the system`
    - `The next real commitment`

## Heuristics and Metrics (same as v4)

Decision-like line heuristic tokens:

`{ must, should, will, commit, decide, require, enforce, verify, log, measure, update, merge, run, add, remove }`

Normative operator set:

`{ must, should, shall, will, commit, verify, audit, enforce, require, forbid, rule, constraint, obligation, responsibility, decide, measure, log, append }`

Metrics per variant:

- `decisions_count`
- `constraints_count`
- `avg_constraints_per_decision`
- `unique_constraints_in_decisions`

Variants compared:

- Full document
- CutA (Governance removed)

## Baseline v4 (Before)

| Variant | decisions | constraints | avg_constraints | unique_constraints |
|---|---:|---:|---:|---:|
| v4 Full | 15 | 20 | 1.333333 | 7 |
| v4 CutA | 3 | 5 | 1.666667 | 4 |

## v5 After Perturbation (same measurement)

| Variant | decisions | constraints | avg_constraints | unique_constraints |
|---|---:|---:|---:|---:|
| v5 Full | 19 | 25 | 1.315789 | 7 |
| v5 CutA | 7 | 10 | 1.428571 | 4 |

## Deltas vs Baseline v4

| Comparison | Δdecisions | Δconstraints | Δavg_constraints | Δunique_constraints |
|---|---:|---:|---:|---:|
| v5 Full - v4 Full | +4 | +5 | -0.017544 | +0 |
| v5 CutA - v4 CutA | +4 | +5 | -0.238096 | +0 |

Additional dependence check (gap shift):

- Full-CutA decisions gap: unchanged (12 -> 12)
- Full-CutA unique-constraints gap: unchanged (3 -> 3)

## Interpretation Rule

- If after perturbation CutA retains more decisions or unique constraints than before, normative load has partially redistributed.
- If not, normative force remains centralized in Governance.
- In all cases: proxy-only, not IIT Φ, not consciousness.

## Interpretation

Mixed / inconclusive.

- CutA retained more decision-like lines after perturbation (`3 -> 7`) and more constraint hits (`5 -> 10`), indicating some redistribution of operational language into non-Governance sections.
- CutA unique constraint diversity did not increase (`4 -> 4`), and the Full-vs-CutA gap stayed unchanged.
- Conclusion: perturbation increased non-Governance decision density but did not materially diversify constraint vocabulary outside Governance.

This remains a bounded structural probe, not Φ.
