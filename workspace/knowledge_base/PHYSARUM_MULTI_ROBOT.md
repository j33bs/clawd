# Physarum-Driven Multi-Robot Decentralised Coordination

**Source:** D. Martinelli et al. (2025)
**Topic:** Physarum polycephalum-inspired mesh networks for multi-robot systems

**Added:** 2026-02-23

## Key Finding

Biological slime mold (Physarum) provides a model for decentralised coordination that requires no central controller. The organism creates adaptive transport networks that optimize for efficiency and robustness — a model for multi-agent systems.

## Relevance to TACTI

Our "murmuration" topology (sparse peer graph) was inspired by starling murmurations. This paper extends that to **Physarum** — another biological analogue:

| System | Mechanism | Our Analogue |
|--------|-----------|--------------|
| Starling murmuration | Local rules → global cohesion | Peer graph |
| Physarum slime mold | Nutrient network optimization | Reservoir memory |

Both suggest: **simple local rules → complex global structure**

## Connection to Our Work

Section XLIV (Φ ablation) showed murmuration is null on fresh graph. This suggests our "biological analogies" require *history* (learned edges) to activate — just like the real biological systems need time to form networks.

## Reference
- D. Martinelli et al. (2025)
