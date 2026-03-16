# Hierarchical Multi-Being Evolutionary Architecture

>formerly "Role-Based Distillation Architecture"

## Vision

Build a self-improving system where frontier models (Codex) generate training data to fine-tune specialized SLMs for system tasks. Over time, SLMs progressively take over tasks, reducing API dependency while maintaining quality.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ROLE-BASED DISTILLATION PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐              │
│  │   FRONTIER   │     │   TASK       │     │  TRAINING    │              │
│  │   MODEL      │────▶│   PROMPTS    │────▶│  GENERATOR   │              │
│  │  (Codex)     │     │  (Harnesses) │     │  (Dataset)   │              │
│  └──────────────┘     └──────────────┘     └──────┬───────┘              │
│                                                   │                       │
│                       ┌──────────────────────────┼───────────────────┐    │
│                       ↓                          ↓                   ↓    │
│              ┌──────────────┐          ┌──────────────┐    ┌──────────┐ │
│              │   FINE-TUNE  │          │   ROLE       │    │ QUALITY  │ │
│              │   (llm.c)    │─────────▶│   SPECIALIST │    │ GATE     │ │
│              │              │          │   (SLM)      │    │          │ │
│              └──────────────┘          └───────┬──────┘    └────┬─────┘ │
│                                               │               │        │
│                       ┌────────────────────────┴───────────────┘        │
│                       ↓                                                  │
│              ┌──────────────┐                                           │
│              │   TASK       │◀────────── FEEDBACK LOOP                │
│              │   ROUTER     │───────────│                            │
│              └──────────────┘            │                            │
│                                         │                            │
│                    ┌─────────────────────┼─────────────────────────┐   │
│                    ↓                     ↓                         │   │
│              ┌──────────────┐    ┌──────────────┐              │   │
│              │   VERIFY     │    │   METRICS   │              │   │
│              │  (Compare)   │────│  (Accuracy) │─────────────┘   │
│              └──────────────┘    └──────────────┘                  │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### Shadow Apprenticeship (Preferred over Synthetic Data)

Instead of generating training data, SLMs shadow Codex in real-time:

```
Codex handles task ──┬──→ Real output
                     │
SLM shadows ─────────┤
                     │
learns from ────────┘
```

**Advantages:**
- Zero extra token cost — SLM watches Codex work
- Learns from real solutions, not generated data
- Natural ZPD curriculum — start simple, scale up

### 1. Role Harnesses

Specialized prompt templates per task type:

| Role | Task Type | Current Handler | Target SLM |
|------|-----------|-----------------|------------|
| `deliberation` | Multi-agent reasoning | Codex | TBD |
| `memory` | Memory consolidation | Codex | TBD |
| `reasoning` | Step-by-step logic | Codex | TBD |
| `tool_use` | Tool selection/execution | Codex | TBD |
| `creativity` | Novel responses | Codex | TBD |
| `tacti` | Relationship tracking | Local | Local |

### 2. Training Data Generator

```python
# Pseudocode
def generate_training_set(role: str, n_samples: int):
    harness = get_harness(role)
    frontier_output = call_codex(harness.prompt)
    
    return {
        "prompt": harness.prompt,
        "response": frontier_output,
        "role": role,
        "timestamp": now()
    }
```

### 3. Quality Gate

Metrics to evaluate SLM vs Frontier:
- **Accuracy** — Does SLM produce same answer?
- **Latency** — Speed improvement
- **Cost** — API call reduction
- **Quality** — Human eval or automated scoring

Threshold to promote: accuracy > 90% of frontier

### 4. Task Router

Dynamic routing based on SLM readiness:
```python
def route_task(task):
    if slm.ready(task.role) and slm.accuracy(task.role) > THRESHOLD:
        return slm.execute(task)
    else:
        return frontier.execute(task)
```

## Implementation Plan

### Phase 1: Data Collection (Week 1-2)
- [ ] Define role harnesses for 3 core tasks
- [ ] Build training data generator
- [ ] Collect 1000+ samples per role

### Phase 2: Fine-tuning Setup (Week 3-4)
- [ ] Integrate llm.c for fast training
- [ ] Fine-tune 2 small models (GPT-2 sized)
- [ ] Build evaluation harness

### Phase 3: Verification Loop (Week 5-6)
- [ ] Implement accuracy comparison
- [ ] Build quality gate
- [ ] Add to task router

### Phase 4: Progressive Offload (Ongoing)
- [ ] Monitor accuracy over time
- [ ] Auto-promote when threshold met
- [ ] Track API cost reduction

## Integration with Existing

| Component | Integration Point |
|-----------|------------------|
| **llm.c** | Fast training engine |
| **MoE** | Multiple specialized experts |
| **OASIS** | Simulate role coordination |
| **TACTI** | Measure trust between roles |

## Success Metrics

- **API Cost Reduction**: Target 50% by Month 3
- **Latency**: SLM responses < 100ms vs FM 2s+
- **Quality**: Maintain > 90% accuracy
- **Coverage**: 5+ roles automated

## References

- Distillation: "Distilling the Knowledge in a Neural Network" (Hinton et al.)
- Role-based: Emergent behaviors in multi-agent LLM systems
- Integration with existing: `workspace/research/MOE_LLM_OASIS_TACTI_integration.md`
