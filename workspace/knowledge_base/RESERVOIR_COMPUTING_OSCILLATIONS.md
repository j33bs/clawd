# Reservoir Computing: Hardware Advances & Oscillations

**Sources:**
- ScienceDirect (2025): "Oscillations enhance time-series prediction in reservoir computing"
- ACS Applied Materials: Various memristor-based reservoir computing papers

**Added:** 2026-02-23

## Key Findings

1. **Physical Reservoirs:** Memristor-based systems achieve 99%+ accuracy on temporal tasks (spoken digit recognition)

2. **Oscillations Enhance Prediction:** Feedback oscillations improve long-term prediction in reservoir computing

3. **Temporal Processing Efficiency:** "Reservoir computing has emerged as an efficient computational paradigm for processing temporal and dynamic data"

## Relevance to TACTI

Our system already has:
- `reservoir.py` — software reservoir
- `oscillatory_gating.py` — oscillatory mechanisms

The research validates this approach and suggests enhancements.

## Novel Idea: Coupled Oscillator Reservoir

Instead of a **single reservoir**, use **multiple reservoirs with phase relationships**:

1. Multiple reservoir nodes at different oscillatory phases
2. Coupling between phases creates interference patterns
3. Could enhance cross-timescale binding (TACTI core)

This is physically motivated: biological neurons oscillate in coupled networks.

## Connection to Cold-Start Problem

Our Φ ablation showed reservoir is "routing-order neutral but response-mode functional." Coupled oscillators could make the routing impact visible — phase relationships create differentiation that normalization doesn't cancel.

## References
- https://www.sciencedirect.com/science/article/pii/S0925231225014006
- https://pubs.acs.org/doi/10.1021/acsami.3c16003
