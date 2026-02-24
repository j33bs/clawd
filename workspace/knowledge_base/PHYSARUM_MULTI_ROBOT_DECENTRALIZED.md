# Physarum Polycephalum for Multi-Robot Decentralized Coordination

**Source:** Nature Scientific Reports (December 2025)
**Title:** "Bioinspired algorithm based on Physarum polycephalum for the formation of decentralized mesh networks in multi-robot systems"

**Added:** 2026-02-24

## Key Innovation

Uses Physarum polycephalum's network formation mechanism for multi-robot coordination:
- Forms robust, adaptive transport networks from local stimuli
- Reinforces useful connections, retracts little-used routes
- Works without centralized infrastructure

## Application

- Port logistics scenarios with autonomous robots
- Mesh network formation for decentralized communication
- Adaptive to topology changes

## Relevance to TACTI

Our "murmuration" topology was inspired by starling flocks. This paper extends that to **Physarum** — another biological analogue:

| System | Mechanism | Application |
|--------|-----------|-------------|
| Starling murmuration | Local cohesion rules | Peer graph (sparse) |
| Physarum slime mold | Nutrient network optimization | Reservoir memory |

The key insight: **local rules → global structure without central control**

## Connection to Our Work

Our Φ ablation showed murmuration is null on fresh graph. This suggests:
- Our biological analogies require **history** (learned edges) to activate
- Just like Physarum networks need time to form

The "decorative vs active" question: Physarum becomes functional only after network formation. Same might be true for our murmuration.

## Reference
- Scientific Reports, December 2025
- doi: 10.1038/s41598-025-33456-y
