# Therapeutic Modalities Micro-Learning System

This track turns the foundation into a **gated micro-lesson curriculum**.

## Design principles

- **Micro-lessons**: one concept per lesson
- **Retrieval first**: short-answer recall before explanation
- **Zone of proximal development**: difficulty rises only when performance supports it
- **Gated progression**: the next lesson does not unlock until the prior lesson is answered
- **Interleaving**: processes, modalities, comparisons, and case formulation are mixed over time
- **Adaptive review**: weak areas are resurfaced earlier and in simpler form

## Files

- `micro_lessons.json` — seeded lesson bank
- `lesson_state.json` — learner state template
- `lesson_engine.py` — scheduler / selector / evaluator

## Lesson flow

1. Deliver one micro-lesson.
2. Wait for learner response.
3. Score response as `incorrect`, `partial`, `solid`, or `strong`.
4. Update proficiency for the underlying skill.
5. Choose the next lesson:
   - same concept, easier/scaffolded if weak
   - same band or slightly harder if partial
   - interleaved adjacent concept if solid
   - higher-difficulty comparison/case lesson if strong

## Difficulty bands

- `1` — recognition / naming
- `2` — mechanism matching
- `3` — compare nearby modalities or processes
- `4` — short case formulation
- `5` — differential selection / integration

## Daily cadence

Recommended: 4–6 lessons per day, spaced across the day.

Default spacing in `lesson_state.json`:
- earliest lesson window: 09:00
- latest lesson window: 19:00
- randomized gap between lessons: 45–180 minutes

## Intended educational outcome

The learner should move from:
- naming modalities
into:
- identifying maintaining processes
- selecting interventions by mechanism
- comparing modalities coherently
- building process-based case formulations
