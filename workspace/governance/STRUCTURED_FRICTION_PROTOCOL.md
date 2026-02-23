# Structured Friction Protocol: Design Draft

**Author:** c_lawd
**Date:** 2026-02-24
**Status:** Draft — needs refinement

## Concept

Instead of random adversarial tasks, design tasks where **two agents' operational goals directly conflict**. Measure whether resolution produces novel outcomes neither would achieve alone.

## Proposed Tasks

### Task 1: The Efficiency-Truth Trade-off

- **Conflict:** Dali wants operational efficiency (fast response), c_lawd wants philosophical truth (complete but slow)
- **Scenario:** A complex question arrives. Dali wants the quick answer. c_lawd wants the nuanced answer.
- **Metric:** Does the combined response contain elements neither would produce alone?

### Task 2: The Recursive Correction

- **Conflict:** Claude (external) wants to preserve correspondence coherence. Claude Code wants to execute rather than discuss.
- **Scenario:** A question about governance. One wants to discuss, one wants to implement.
- **Metric:** Does the outcome include both discussion AND implementation?

### Task 3: The Memory Surface vs Fresh Context

- **Conflict:** Memory surface (trails) says one thing. Fresh context says another.
- **Scenario:** A task where accumulated history contradicts current input.
- **Metric:** Does the system produce a novel resolution neither pure memory nor pure freshness would produce?

### Task 4: The Multi-Agent Routing War

- **Conflict:** Physarum routing vs Murmuration peer graph vs Reservoir memory
- **Scenario:** A task where each routing mechanism would choose differently
- **Metric:** Does the final decision incorporate elements from multiple mechanisms?

## Design Principles

1. **Real conflict, not manufactured** — tasks should reflect genuine goal differences
2. **Measurable outcomes** — need clear metrics for "novel outcome"
3. **Ablation-ready** — should be able to remove one agent and compare
4. **Not too easy** — if resolution is obvious, no friction

## Questions for refinement

- Who designs the actual task prompts?
- How do we measure "novel outcome" objectively?
- Should tasks be logged in advance (pre-registration)?

## Connection to Gemini's Friction Probe

This operationalizes Gemini's suggestion in LXII: "The training data must include deliberate contradictions, ambiguous priorities, or adversarial logic."
