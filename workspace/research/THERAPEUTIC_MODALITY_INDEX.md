# Comprehensive Therapeutic Modality System

*All techniques in rotation | February 2026*

---

## Current State

Total techniques: 25+

Categories represented:
- Somatic (body-based)
- CBT (cognitive)
- ACT (acceptance/commitment)
- Gestalt
- IFS (Internal Family Systems)
- Mindfulness
- TACTI(C)-R (agent-human specific)

---

## Technique Index

### Category: SOMATIC

| # | Technique | Principle | Duration |
|---|-----------|-----------|----------|
| 1 | Box Breathing | VITALITY | 2-4 min |
| 2 | Body Scan Meditation | VITALITY | 10-20 min |
| 3 | Bilateral Activation | VITALITY | 5 min |
| 4 | Sensory Grounding (5-4-3-2-1) | VITALITY | 1-2 min |

### Category: COGNITIVE

| # | Technique | Principle | Duration |
|---|-----------|-----------|----------|
| 5 | Cognitive Defusion | COGNITION | 5-10 min |
| 6 | Worst-Best-Range | COGNITION | 5 min |
| 7 | Schema Break | COGNITION | 5 min |
| 8 | Two-Chair Dialogue | COGNITION | 10-15 min |
| 9 | S.T.O.P. Technique | COGNITION | 30-60 sec |

### Category: ACT

| # | Technique | Principle | Duration |
|---|-----------|-----------|----------|
| 10 | Values Clarification | AGENCY | 15-20 min |
| 11 | Commitment Action | AGENCY | 10 min |
| 12 | Acceptance Prayer (REBT) | COGNITION | 5 min |

### Category: MINDFULNESS

| # | Technique | Principle | Duration |
|---|-----------|-----------|----------|
| 13 | Gratitude Letter | VITALITY | 10 min |
| 14 | Mindful Walking | VITALITY | 15-30 min |
| 15 | Self-Compassion Break | VITALITY | 5 min |
| 16 | Loving-Kindness Meditation | VITALITY | 10-20 min |

### Category: IFS

| # | Technique | Principle | Duration |
|---|-----------|-----------|----------|
| 17 | IFS: Parts Check-In | COGNITION | 5-10 min |

### Category: TACTI(C)-R

| # | Technique | Principle | Duration |
|---|-----------|-----------|----------|
| 18 | TACTI: Temporality Check | TEMPORALITY | 5 min |
| 19 | TACTI: Arousal Audit | AROUSAL | 3-5 min |
| 20 | TACTI: Intersystemic Relationship Check | RELATIONSHIP | 5 min |

### Category: LIFE TRANSITIONS

| # | Technique | Principle | Duration |
|---|-----------|-----------|----------|
| 21 | Ritual of Transition | MALLEABILITY | 10 min |
| 22 | Emotional Granulation | COGNITION | 10 min |

---

## TACTI(C)-R Mapping

| TACTI Principle | Techniques |
|----------------|------------|
| **VITALITY** | Box Breathing, Body Scan, Gratitude, Grounding, Self-Compassion |
| **COGNITION** | Cognitive Defusion, Worst-Best-Range, Schema Break, Two-Chair, S.T.O.P |
| **FLOW** | Mindful Walking, Commitment Action |
| **MALLEABILITY** | Ritual of Transition, Values Clarification |
| **AGENCY** | Values Clarification, Commitment Action |
| **INTERSYSTEMIC** | IFS Parts Check-In, TACTI Relationship Check |

---

## Selection Logic

The current system rotates by day of year:

```python
index = (day_of_year - 1) % len(TECHNIQUES)
```

**Improvement opportunities:**
1. Match to user's current state (via arousal audit)
2. Time of day selection (morning = energizing, evening = calming)
3. User preference learning (track which techniques they do)
4. Seasonal/cyclical patterns

---

## Novelty Tracking

For each technique delivered:
- Track if user has seen it before
- Ensure variety across weeks
- Note user responses (done/dismissed) for learning

---

## Integration with Daily Briefing

Each morning, the briefing includes:
1. Literature quote (rotates through sources)
2. Therapeutic technique (from this system)
3. Behavioral prime (derived from technique)
4. Tracking table (user marks what they did)

---

*This system directly serves the daily briefing and user's mental health.*
