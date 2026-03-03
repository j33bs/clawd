# Φ Proxy Session v2 (Toy Structure-Sensitivity Probe, Not IIT Φ)

Date (UTC): 2026-02-23T11:13:32Z
Baseline commit: 0da938b
Input: `workspace/governance/OPEN_QUESTIONS.md`

## Session Definition

- Partition the document by active markdown heading context into four buckets:
  - A) Governance & Alignment
  - B) Identity & Becoming
  - C) TACTI Framework
  - D) Everything else
- Deterministic heading-to-bucket mapping used in this run:
  - A if heading text contains one of: `governance & alignment`, `guiding principle`, `instrumentation index`, `audit hook`, `decision rule`
  - B if heading text contains one of: `identity & becoming`, `identity`, `becoming`, `character of the system`, `edit-is-identity`
  - C if heading text contains one of: `tacti framework`, `tacti`
  - Otherwise D
- Tokenization: lowercase, split on non-letters, drop tokens shorter than 3 chars.

This is a proxy ritual. It is not IIT Φ and not a consciousness claim.

## Metric Definition

For non-empty section token sets:

- `overlap(i, j) = |tokens_i ∩ tokens_j| / min(|tokens_i|, |tokens_j|)`
- `Coupling_full = average overlap across all available section pairs`

Cuts:

- remove A -> `Coupling_cutA`
- remove B -> `Coupling_cutB`
- remove C -> `Coupling_cutC`

Deltas:

- `ΔA = Coupling_cutA - Coupling_full`
- `ΔB = Coupling_cutB - Coupling_full`
- `ΔC = Coupling_cutC - Coupling_full`

Interpretation rule:

- If all `Δ ≈ 0`: inconclusive (lexically decoupled or metric too weak).
- If any `Δ << 0`: that removed section contributed to cross-section coupling in this crude lexical sense.
- Not Φ, not consciousness; structure-sensitivity only.

## Results

Token set sizes:

- A: 178
- B: 28
- C: 0
- D: 172

Pair overlaps used in `Coupling_full`:

- overlap(A,B) = 0.285714
- overlap(A,D) = 0.331395
- overlap(B,D) = 0.428571

| Metric | Value |
|---|---:|
| Coupling_full | 0.348560 |
| Coupling_cutA | 0.428571 |
| Coupling_cutB | 0.331395 |
| Coupling_cutC | 0.348560 |
| ΔA | +0.080011 |
| ΔB | -0.017165 |
| ΔC | +0.000000 |

## Interpretation

Inconclusive, proxy-only.

- Non-flat signal exists (`ΔA` and `ΔB` are non-zero), but effect sizes are small and lexical.
- `C` had no matched heading context in this document shape, so `ΔC` remained zero.
- This run is a bounded evidence ritual, not an IIT Φ measurement.

## Next Step

Keep this as a lightweight structural integrity signal unless/until an explicit IIT-capable measurement stack is adopted.
