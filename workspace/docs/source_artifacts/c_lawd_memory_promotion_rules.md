# c_lawd Conversation-to-Memory Promotion Rules

## Purpose

These rules decide when live interaction content should leave transient chat state and become durable memory.

## Promote when

Promote a candidate when at least one of these is true:

- it changes future behavior,
- it captures a durable user preference,
- it records a standing commitment,
- it documents a stable doctrine or operating rule,
- it preserves a verified fact worth reusing.

## Do not promote when

- the content is only conversational filler,
- the claim is unsupported and still speculative,
- the note is useful only for the current turn,
- the same meaning is already stored in stronger form.

## Required checks

Before promotion, confirm:

1. `meaning`
   The durable takeaway is explicit.
2. `evidence`
   There is at least one supporting trace, artifact, or human statement.
3. `scope`
   The memory is scoped correctly: repo, surface, agent, user, or chat.
4. `collision`
   The candidate does not silently contradict an existing durable memory.
5. `agency`
   If the content is sensitive or consequential, operator review is required.

## Promotion result states

- `admitted`
- `rejected`
- `needs_review`
- `superseded`

## Minimal record

```yaml
summary: durable meaning
kind: observation|commitment|doctrine|preference
scope: repo|surface|agent|user|chat
evidence:
  - path or source reference
status: admitted|rejected|needs_review|superseded
```
