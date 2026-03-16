# Data governance and teacher-output policy

## Non-negotiable rule

Before logging any model output for later training, classify the source into one of:

- permissive open-weight teacher
- internal human-authored gold label
- external proprietary teacher

Only the first two should enter a local-model distillation corpus by default.

## Required controls

- source provenance for every example
- licence / terms label per example
- opt-out switch at capture time
- hash-based deduplication
- redaction pass for secrets / PII
- approval for promotion into training data
- immutable eval set separated from training set

## Practical replacement for naive shadow learning

Instead of “record everything the frontier model says and train the local models on it”, use:

1. curated gold tasks
2. human-accepted local trajectories
3. open-teacher preference pairs
4. post-hoc failure review and repair
5. DPO / preference optimization only after SFT is stable
