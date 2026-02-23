# Nested Learning: A New ML Paradigm for Continual Learning

**Source:** Google Research Blog (2025)
**Added:** 2026-02-24

## Key Innovation

**Nested Learning** — a new ML paradigm that addresses catastrophic forgetting by recognizing that **architecture and optimization are the same concept at different levels**:

- Architecture = "level of optimization"
- Optimization algorithm = "level of learning"
- Both have "context flow" and different update rates

## The Insight

> "By recognizing this inherent structure, Nested Learning provides a new, previously invisible dimension for designing more capable AI... helping solve issues like catastrophic forgetting."

## Relevance to TACTI

This connects to our **memory consolidation** question:
- Catastrophic forgetting = when new learning destroys old memory
- Our reservoir should prevent this
- Nested Learning suggests: architecture and learning are the same problem at different scales

## Connection to Our Work

Our **sleep consolidation protocol** (from LXIV) was about periodic replay to strengthen memories. Nested Learning provides a theoretical foundation: the "architecture = optimization at different level" insight suggests our reservoir could be a different "level" of learning, not just memory storage.

## Quote

> "We argue that the model's architecture and the rules used to train it (i.e., the optimization algorithm) are fundamentally the same concepts; they are just different 'levels' of optimization."

## Reference
- https://research.google/blog/introducing-nested-learning-a-new-ml-paradigm-for-continual-learning/
