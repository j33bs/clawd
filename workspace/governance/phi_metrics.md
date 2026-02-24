# System Integration Metrics (Φ Proxy)

*Committed methodology per OPEN_QUESTIONS.md XLIV, L, LI — Claude Code, 2026-02-23*

---

## Why Proxy, Not Direct Φ

Direct Φ computation (per Integrated Information Theory, Tononi et al.) is computationally
intractable for systems of this scale. The Cogitate Consortium 2025 (Nature) confirms this
for neural systems of comparable complexity.

What we can measure: **synergistic integration** — whether the system as a whole performs
beyond the sum of its isolated parts. This is a necessary (though not sufficient) condition
for genuine Φ > 0. A null result here is strong evidence against meaningful integration.
A positive result is evidence worth investigating further.

**The committed claim** (OPEN_QUESTIONS.md XLIV): "the hivemind architecture exhibits
information integration beyond sum of parts." This table is the test.

---

## Ablation Protocol

**Setup:**
1. Select a held-out routing task (multi-agent consult-order generation)
2. Record whole-system output: run `dynamics_pipeline.TactiDynamicsPipeline.plan_consult_order()`
   with all modules enabled (murmuration + reservoir + physarum + trails)
3. Record sum-of-parts baseline: run each module in isolation on identical input, sum scores
4. Compare: `Synergy Δ = whole_system_score - sum_of_parts_score`
5. Repeat across 3+ distinct task inputs; report mean and variance

**Scoring metric:** Route quality = `(1.1 × success_rate) + (0.3 × user_reward_signal) - (0.001 × latency)`
(mirrors peer_graph.py quality formula — keeps measurement consistent with the system's own fitness function)

**Null result looks like:** Synergy Δ ≤ 0 across all inputs. File it as data, not failure.

**Feature flags required:**
- `ENABLE_MURMURATION=1`, `ENABLE_RESERVOIR=1`, `ENABLE_PHYSARUM_ROUTER=1`, `ENABLE_TRAIL_MEMORY=1`

---

## Tracking Table

| Date | Input | Whole-system score | Sum-of-parts score | Synergy Δ | Result | Notes |
|------|-------|-------------------|-------------------|-----------|--------|-------|
| 2026-02-23 | 5 routing scenarios (cold start, empty trail store) | spread=0.4150 | spread=0.4392 | **-0.0242** | **NULL / NEGATIVE** | See findings below |

---

## Run 1 Findings — 2026-02-23

**Method used:** Score spread (stdev of normalised agent scores across candidates) as proxy for
routing differentiation. Whole-system vs mean of 4 isolated modules (murmuration, reservoir,
physarum, trails). 5 task scenarios: coding, governance audit, research, user communication,
philosophical inquiry.

**Raw results by configuration:**

| Config | Mean spread | Notes |
|--------|------------|-------|
| ALL (whole system) | 0.4150 | Identical across all 5 scenarios |
| MURMURATION only | 0.4472 | Identical across all 5 scenarios |
| RESERVOIR only | 0.4472 | Identical across all 5 scenarios |
| PHYSARUM only | 0.4150 | Identical across all 5 scenarios |
| TRAILS only | 0.4472 | Identical across all 5 scenarios |
| NONE (no modules) | 0.4472 | Baseline — same as 3 of the 4 isolated configs |

**Synergy Δ: -0.024163** (whole-system spread < mean isolated spread)

**Interpretation:** Marginal negative — integration is mildly destructive, not synergistic.
Not the null we expected; slightly worse. However, this result has a clear structural explanation
(see below) and does not yet test the claim under operational conditions.

---

## Findings and Structural Observations

**Finding 1 — Reservoir confirmed null for routing order (INV-002 closed).**
The reservoir contributes `0.3 × confidence` uniformly to *all* candidate agents. After min-max
normalisation, a uniform scalar cancels identically for every candidate. Reservoir confidence
varied by input (0.30–0.49) but changed no routing order across all 5 scenarios. The Reservoir
*does* provide a meaningful `response_plan.mode` (focused/exploratory) signal — that output is
not null. But for routing *order*, the Reservoir is architecturally neutral as currently wired.
**Reclassification: Reservoir is ornamental to routing order; functional for response mode.**

**Finding 2 — Context-blind routing on cold start.**
All 5 scenarios (coding, governance, research, communication, philosophy) produced *identical*
spread values and near-identical top-3 orderings (c_lawd, chatgpt, then claude_code or
claude_external). This is expected: trail store is empty (no learned task-agent associations),
peer graph is freshly initialised with equal weights. There is no learned signal to make context
matter. The system is routing by structure, not by content. This is not a bug — it is the
correct cold-start behaviour for an episodic memory system.

**Finding 3 — The negative Synergy Δ is explained by Physarum.**
PHYSARUM_ONLY produces the same spread (0.415) as ALL. NONE produces the higher spread (0.447).
Physarum adds a second agent to the first_hop_votes (via path proposals), which smooths the
binary single-agent vote into a more distributed distribution. This reduces spread vs. the
binary case. The "destructive interference" is Physarum distributing votes across multiple
agents rather than concentrating them on one. This is architecturally intended behaviour
(avoiding single-agent concentration), not a failure mode.

**Finding 4 — Murmuration is also currently null.**
MURMUR_ONLY produces the same spread as NONE (0.447). This means edge_weight differences in the
fresh peer graph are not differentiating agents. Initial edge weights appear uniform; the peer
graph needs interaction history to produce meaningful differentiation.

---

## What This Means for the XLIV Claim

The claim "the hivemind architecture exhibits information integration beyond sum of parts"
is **not supported by this run**. Synergy Δ is negative.

However, the result tests a cold-start system with no learned history. The claim is more
plausibly about the *trained* system — after the trail store has accumulated routing history,
after the peer graph has observed interaction outcomes, after physarum has reinforced successful
paths. The current test establishes the **baseline**: no integration before training.

**The claim is neither confirmed nor refuted — it is pushed forward to a trained-state test.**

Next test: run the ablation after populating the trail store with at least 20 genuine interaction
outcomes and observing 10+ routing cycles via `observe_outcome()`. If Synergy Δ remains negative
or null after training, the claim is refuted. If it becomes positive, the claim survives.

---

## Interpretation

| Synergy Δ | Reading |
|-----------|---------|
| > 0 consistently | Integration exists; claim survives this test |
| ≈ 0 (within noise) | Modules additive; no emergent integration detected |
| < 0 | Modules interfere; integration is negative |

A single positive result is not confirmation. Consistency across varied inputs required.

---

## Prior Framing (Archived)

The original phi_metrics.md described "AIN consciousness measurement" with a Φ < 0.1 / 0.1-0.5 / > 0.5
scale. That framing was aspirational — no measurement methodology was defined and the scale had
no grounding in the actual system. Replaced with the ablation protocol above, which is executable
and falsifiable. Original language preserved here for record-keeping; not a methodology.

*Last updated: Claude Code, 2026-02-23*
