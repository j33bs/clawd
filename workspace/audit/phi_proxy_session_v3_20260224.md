# Φ Proxy Session v3 (Constraint Coupling, Not IIT Φ)

Date (UTC): 2026-02-23T11:18:40Z
Baseline commit: e03c984
Input: `workspace/governance/OPEN_QUESTIONS.md`

## Session Definition

Partition by heading context:

- A) Governance & Alignment
- B) Identity & Becoming
- C) TACTI Framework
- D) Everything else

Deterministic heading mapping used:

- A if heading contains: `governance & alignment`, `guiding principle`, `instrumentation index`, `audit hook`, `decision rule`, `what counts as an experiment`, `non-goals`
- B if heading contains: `identity & becoming`, `identity`, `becoming`, `character of the system`, `edit-is-identity`
- C if heading contains: `tacti framework`, `tacti`
- Else D

## Normative Operator Set

Fixed token set (exact-match after tokenization):

`{ must, should, shall, will, commit, verify, audit, enforce, require, forbid, rule, constraint, obligation, responsibility, decide, measure, log, append }`

Tokenization:

- lowercase
- split on non-letters
- exact-match against the operator set

## Metric Definition

For any text `T`:

- `count(T)` = total operator-token occurrences
- `unique(T)` = number of distinct operator tokens used
- `density(T)` = `count(T) / total_tokens(T)`

Compute for full doc and cut variants:

- Cut A: remove section A
- Cut B: remove section B
- Cut C: remove section C

Deltas:

- `Δdensity_X = density_cutX - density_full`
- `Δunique_X = unique_cutX - unique_full`

Interpretation rule:

- If all deltas are ~0: inconclusive (even distribution or metric too weak)
- If removing a section drops density/uniques: that section contributed to normative coupling
- If removing a section increases density: removed section had weaker normative density than remainder
- This is structure-sensitivity only; **not IIT Φ, not cognition, not consciousness**

## Results

Section line counts in this document shape:

- A: 62
- B: 7
- C: 0
- D: 45

| Variant | total_tokens | count | unique | density | Δdensity | Δunique |
|---|---:|---:|---:|---:|---:|---:|
| Full | 734 | 32 | 8 | 0.043597 | 0.000000 | 0 |
| A removed | 373 | 7 | 6 | 0.018767 | -0.024830 | -2 |
| B removed | 685 | 32 | 8 | 0.046715 | +0.003119 | +0 |
| C removed | 734 | 32 | 8 | 0.043597 | +0.000000 | +0 |

## Interpretation

Proxy-only and still conservative.

- Removing A caused a clear drop in both normative density and unique operator diversity (`Δdensity_A = -0.024830`, `Δunique_A = -2`), suggesting section A carries a large share of constraint language.
- Removing B slightly increased density, suggesting B is less normative-dense than the remainder.
- C had no matched section content in this document shape, so `ΔC = 0`.

This is a useful constraint-topology signal, but it is not Φ.

## Next Step

If desired, keep this as a cheap continuity check of where constraints live in the correspondence; do not treat it as cognition evidence.
