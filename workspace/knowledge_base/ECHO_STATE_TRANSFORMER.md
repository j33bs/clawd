# Echo State Transformer: Reservoir + Attention Hybrid

**Source:** arXiv 2507.02917 (2025/2026)
**Authors:** Yannis Bendi-Ouis, Xavier Hinaut (Inria Bordeaux — Mnemosyne team)

**Added:** 2026-02-23

## Key Innovation

Interleaves **fixed random recurrent reservoirs** with **transformer attention**:
- Linear complexity (not quadratic)
- Preserves temporal memory from reservoir
- Achieves competitive performance on classification and anomaly detection

## Relevance to TACTI

Our reservoir module faces the "decorative vs active" question (Sections III, XL). This paper shows:
- Reservoirs CAN be integrated with transformers effectively
- The key is proper wiring to downstream tasks
- Echo State Transformer solves the efficiency problem while maintaining memory

## Connection to Our Work

The "decorative vs active" debate: this paper suggests the issue is **wiring**, not the reservoir itself. If our reservoir contributes uniform scalars that normalize away (as found in INV-002), the fix might be architectural — not removing the reservoir, but changing how its output feeds into routing.

## References
- arXiv:2507.02917
- Time Series Library benchmarks
