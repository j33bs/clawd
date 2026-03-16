# Audit of the original HMBEA plan

## Strong ideas worth keeping

- role specialization
- progressive local offload
- explicit accuracy / latency targets
- shadow evaluation before promotion
- a staged roadmap rather than an immediate full replacement of frontier models

## Primary faults

1. **The plan overstates feasible parallelism on a single 3090.**
   “2x 27B in parallel” is not a sound baseline for a 24 GB card once real runtime overhead, KV cache, context, and tool latency are counted.

2. **It confuses logical multi-agent structure with physically resident multi-model execution.**
   On one GPU, those should not be treated as the same design problem.

3. **It omits production controls.**
   Missing: versioned prompts, schema validation, test gates, rollback criteria, traceability, least-privilege tool policy, approval interrupts, supply-chain pinning, and prompt-injection handling.

4. **OASIS is on the critical path without a direct fit.**
   Social simulation is not the right first dependency for code / research / orchestration reliability.

5. **TACTI is underspecified.**
   Without a stable public specification, it should be treated as an optional metrics adapter rather than a foundational dependency.

6. **The metrics are too coarse.**
   You need per-domain acceptance rates, escalation rate, schema-valid rate, tool-call precision, unit-test pass rate, p50/p95 latency, and regression gates.

7. **The training / shadowing loop is legally and operationally underdefined.**
   A teacher-output capture policy is required before any distillation workflow is implemented.

## Revised principle

Start with a **deterministic supervisor graph + one strong local generalist**.
Add a code specialist only after the graph, retrieval, validation, and escalation rules are already reliable.
