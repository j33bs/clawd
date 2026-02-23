# Φ Proxy Session v4 (Constraint Influence, Not IIT Φ)

Date (UTC): 2026-02-23T11:25:41Z
Baseline commit: 8bd79bc
Input: `workspace/governance/OPEN_QUESTIONS.md`

## Session Definition

Partition:

- A) Governance & Alignment section(s)
- B) The rest of the document

Deterministic mapping for this document shape:

- A if heading contains: `governance & alignment`, `guiding principle`, `status tags`, `instrumentation index`, `decision rule`, `what counts as an experiment`, `audit hook`, `non-goals`
- Else B

## Decision-like Statement Heuristic

Line is decision-like if it contains at least one of:

`{ must, should, will, commit, decide, require, enforce, verify, log, measure, update, merge, run, add, remove }`

Extraction scope:

- Body lines only (headings excluded)
- Full document and CutA (A removed)

## Normative Operator Set (for counting constraints)

`{ must, should, shall, will, commit, verify, audit, enforce, require, forbid, rule, constraint, obligation, responsibility, decide, measure, log, append }`

Tokenization:

- lowercase
- split on non-letters
- exact-match to the sets above

## Metric Definition

For each variant (Full, CutA):

- `decisions_count` = number of decision-like lines
- `constraints_count` = total normative operator token hits inside decision-like lines
- `avg_constraints_per_decision` = `constraints_count / max(decisions_count, 1)`
- `unique_constraints_in_decisions` = distinct normative operators seen in decision-like lines

Deltas:

- `Δdecisions = decisions_cutA - decisions_full`
- `Δavg_constraints = avg_cutA - avg_full`
- `Δunique_constraints = unique_cutA - unique_full`

Interpretation rule:

- If removing Governance drops decisions/avg/unique, Governance exerts constraint influence.
- If little change, influence is weak or internalized elsewhere.
- This is a constraint-influence sensitivity probe, not IIT Φ.

## Results

Section line counts:

- A: 62
- B: 52

| Variant | decisions | constraints | avg_constraints | unique_constraints |
|---|---:|---:|---:|---:|
| Full | 15 | 20 | 1.333333 | 7 |
| CutA (Governance removed) | 3 | 5 | 1.666667 | 4 |
| Δ (CutA - Full) | -12 | -15 | +0.333333 | -3 |

## Interpretation

Proxy-only, conservative.

- Removing Governance greatly reduced the count of decision-like lines (`Δdecisions = -12`) and reduced unique normative operators (`Δunique_constraints = -3`).
- Average constraints per remaining decision line increased (`Δavg_constraints = +0.333333`), suggesting fewer but denser decision lines in the remainder.
- This indicates governance language influences the visibility and diversity of decisions, but this is still lexical/proxy evidence only.

Not Φ, not cognition, not consciousness.

## Note

This run makes constraint influence inspectable without escalating complexity.
