# c_lawd Feel-Together State Model

## Purpose

This spec defines the relational state Source should track when the work is not only technical, but also attunement-sensitive.

## Core dimensions

- `trust_state`: `building | stable | degraded | repairing`
- `arousal_level`: `low | steady | elevated | overloaded`
- `novelty_level`: `routine | fresh | destabilizing`
- `coherence_level`: `clear | mixed | fractured`
- `repair_status`: `not_needed | invited | in_progress | restored`

## State meanings

### trust_state

- `building`: rapport is forming but not yet durable.
- `stable`: expectations and interpretation are holding.
- `degraded`: rupture, mismatch, or repeated friction is active.
- `repairing`: trust is not restored yet, but repair work is underway.

### arousal_level

- `low`: energy or urgency too low for crisp coordination.
- `steady`: workable operating range.
- `elevated`: urgency is useful but narrowing attention.
- `overloaded`: signal quality is degraded by intensity.

### novelty_level

- `routine`: known terrain.
- `fresh`: real newness without disorientation.
- `destabilizing`: novelty is outrunning shared orientation.

### coherence_level

- `clear`: question, evidence, and next step line up.
- `mixed`: partial alignment with visible slippage.
- `fractured`: parties are operating on incompatible frames.

## Transition rules

- `degraded -> repairing` requires an explicit acknowledgment of rupture.
- `repairing -> stable` requires a concrete behavior change plus confirmation that it landed.
- `overloaded` should block irreversible decisions unless the operator explicitly overrides.
- `fractured` should trigger clarification before more synthesis.

## Emission guidance

The state model is most useful when attached to:

- mission handoffs,
- durable memory promotion candidates,
- postmortems for misunderstandings,
- operator-visible status summaries.
