# c_lawd Memory Meaning Layer

## Purpose

This document defines what kinds of things count as memory-worthy inside Source, and how they differ from transient chat.

## Memory classes

### Observation

A grounded fact about the world, repo, runtime, or user context.

- Must be attributable to evidence.
- Can be revised when contradicted.

### Commitment

A promised future action, constraint, or standing instruction.

- Must name an owner.
- Must remain visible until satisfied, revoked, or replaced.

### Doctrine

A durable rule about how Source should think, act, or govern itself.

- Higher weight than a single observation.
- Changed only by explicit supersession, not accidental drift.

### Preference

A stable user or system preference that shapes defaults.

- Should include scope.
- Must not silently promote into doctrine.

### Working note

A transient aid that helps during execution but should not be treated as durable truth.

- Safe to discard.
- Not a commitment unless explicitly promoted.

## Promotion boundary

Conversation content becomes durable only when it crosses at least one of these thresholds:

- it changes future behavior,
- it constrains future decisions,
- it records a verified fact worth reusing,
- it captures a rupture/repair signal that affects coordination.

## Contradiction handling

- Observations can be falsified.
- Commitments can be completed, revoked, or superseded.
- Doctrine can be amended only by explicit replacement.
- Preferences can be scoped, dated, or retired.

## Minimal memory envelope

```yaml
kind: observation|commitment|doctrine|preference|working_note
summary: concise durable meaning
evidence:
  - path, test, runtime trace, or human statement
scope: repo|surface|agent|user|chat
status: active|completed|revoked|superseded|discarded
```
