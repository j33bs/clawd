# Liquid Neural Networks: Continuous-Time Adaptive AI

**Sources:** 
- Liquid AI (liquid.ai)
- ScienceDirect (December 2025)
- Various 2025 articles

**Added:** 2026-02-24

## Key Innovation

Liquid neural networks (LNNs) are **brain-inspired systems that can stay adaptable and robust to changes even after training**:

- **Continuous-time dynamics** — differential equations that evolve continuously over time (not discrete steps)
- **Adaptive time constants** — bounded, stable dynamics that filter noise
- **Post-training adaptation** — unlike traditional networks, can adapt without retraining
- **Efficient for edge** — works well on resource-constrained devices

## Relevance to TACTI

This is directly relevant to our **cross-timescale processing** core:

1. **Continuous time** — LNNs process time as continuous, not discrete tokens
2. **Adaptive dynamics** — our arousal system could use similar gating
3. **Post-training adaptation** — connects to our "reservoir learns over time" question

## Connection to Reservoir Computing

LNNs share DNA with reservoir computing:
- Fixed random recurrent connections
- Time-continuous dynamics
- Adaptive output layer

But LNNs add: **continuous-time differential equations** as the backbone.

## Quote

> "Their continuous-time formulations enable bounded, stable dynamics that filter out sensor noise and electrical interference, while adaptive time constants..."

## Future: Liquid Foundation Models

Liquid AI is extending to "Liquid Foundation Models" — continuous-time foundation models that adapt to new tasks without fine-tuning.

## Reference
- https://www.liquid.ai/research/liquid-neural-networks-research
