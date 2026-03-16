# c_lawd Think-Together Contract

## Purpose

This contract defines the minimum shape of a shared inquiry so Source can turn conversation into a reusable thinking trace instead of a one-off reply.

## Required moves

Every think-together pass should produce these elements in order:

1. `question`
   The real problem being answered in one sentence.
2. `hypothesis`
   The current best model or framing.
3. `evidence`
   Concrete observations, files, tests, or prior commitments that support or constrain the hypothesis.
4. `uncertainty`
   What is still unknown, inferred, or weakly evidenced.
5. `synthesis`
   The integrated read after weighing evidence against uncertainty.
6. `decision`
   The next action, non-action, or explicit defer.

## Constraints

- Evidence must stay distinguishable from inference.
- Uncertainty must not be collapsed into narrative confidence.
- A decision is optional only when the correct result is `defer` with a stated reason.
- If the inquiry changes system state, the affected artifact or interface must be named.

## Minimal record shape

```yaml
question: >
  What are we actually trying to resolve?
hypothesis: >
  Current best framing.
evidence:
  - kind: file|test|runtime|memory|human
    ref: path-or-handle
    note: why it matters
uncertainty:
  - specific unknown or unresolved risk
synthesis: >
  Integrated read after weighing the evidence.
decision:
  action: do|defer|ask|stop
  owner: c_lawd|Dali|jeebs|shared
  artifact: optional path
```

## Acceptance

The contract is satisfied when another being can read the record and recover:

- what was asked,
- what evidence constrained the answer,
- where uncertainty remains,
- what should happen next.
