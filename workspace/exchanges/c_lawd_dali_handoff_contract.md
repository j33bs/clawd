# c_lawd <-> Dali Handoff Contract

## Purpose

This contract defines the minimal envelope for handing work between the relational lane (`c_lawd`) and the runtime/orchestration lane (`Dali`) without losing intent, evidence, or expected return shape.

## Required fields

```yaml
handoff_id: unique string
timestamp: ISO-8601
from_agent: c_lawd|Dali
to_agent: c_lawd|Dali
task_id: Source mission task id
intent: one-sentence goal
context:
  summary: concise background
  refs:
    - relevant file or runtime reference
evidence:
  - concrete artifact, test, or observation
uncertainty:
  - open risk or unknown
expected_return:
  kind: result|blocker|question
  artifact: optional path
  summary_shape: one sentence
```

## Rules

- Intent must be actionable, not atmospheric.
- Evidence must point to concrete repo or runtime state.
- Uncertainty must survive the handoff intact.
- Return payloads must say whether the work advanced, blocked, or changed shape.

## Return markers

- `result`: concrete progress was made and should be reviewed or continued.
- `blocker`: progress stopped on a named constraint.
- `question`: the receiving lane needs a decision or clarification before continuing.

## Source UI binding

When Source UI records a handoff, it should preserve:

- `from_agent`
- `to_agent`
- `task_id`
- `summary`
- `kind`
- `timestamp`
- minimal provenance such as runtime agent or source subsystem
