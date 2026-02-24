# Agent Output: Dali

- session: A (isolated)
- timestamp_utc: 2026-02-24T09:25:56Z

1) Admit only append-only artifacts and timestamp every gate decision.
2) Use one signed audit entry per run; reject mutable side channels.
3) Falsifiable test: rerun gate set on same corpus; hash and gate verdicts must match exactly.
4) If hashes diverge, mark FAIL and quarantine outputs pending human review.
5) Non-goal: maximizing narrative richness or stylistic detail in this memo.
6) Token budget priority: concise controls over explanatory breadth.
