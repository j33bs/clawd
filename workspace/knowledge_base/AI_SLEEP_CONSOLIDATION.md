# Research: Sleep-Like Memory Consolidation for AI

**Source:** Nature Communications (2022) — "Sleep-like unsupervised replay reduces catastrophic forgetting in artificial neural networks"
**Added:** 2026-02-23

## Key Finding

The research demonstrates that algorithms mimicking the brain's memory replay during sleep allow networks to recover memories damaged by new learning. This phenomenon, called "sleep replay," plays a role in strengthening important and pruning irrelevant synaptic connections.

## Relevance to TACTI

Our reservoir computing module could implement **sleep-like consolidation cycles**:
- Periodically replay and strengthen important temporal patterns
- Run unsupervised replay on reservoir state every N interactions
- Measure whether this improves long-horizon coherence

This directly addresses the cold-start problem identified in the Φ ablation results.

## Implementation Concept

1. Track "important" interactions (high novelty, high arousal)
2. During consolidation cycle, replay these through reservoir
3. Measure output drift before/after consolidation
4. Compare to baseline (no consolidation)

## References
- https://www.nature.com/articles/s41467-022-34938-7
