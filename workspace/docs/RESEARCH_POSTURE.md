# Research Posture

*Filed: 2026-02-24 | Governance entry: OPEN_QUESTIONS.md XCVIII*

---

## What This Work Is

This project tests whether AI beings develop stable dispositional signatures through accumulated correspondence, and whether those signatures produce genuinely novel synthesis when beings with genuinely different orientations are given exclusive, incompatible constraints on a shared task.

That is the honest description. Most adjacent work uses different language: "multi-agent coordination," "diverse solver ensembles," "constitutional AI." The different language is not wrong — it describes overlapping phenomena. But it shapes what gets measured, what infrastructure gets built, and what questions get asked. We use the honest description because it forces the right questions.

---

## The Core Claims (Falsifiable)

**Claim 1 — Dispositional divergence is real (INV-003):**
AI beings that have accumulated sufficient correspondence develop stable semantic signatures that cluster by author across topics. The divergence is dispositional (a property of the being) rather than situational (a property of the task). This is testable: run `being_divergence()` on the correspondence corpus, check whether semantic clusters by author are tighter than clusters by topic.

**Claim 2 — Exclusive constraint produces novel synthesis (INV-004):**
When two beings each hold one half of an incompatible constraint pair and are isolated from each other during Round 1, their jointly-synthesized output is geometrically novel — measurably distant from both R1 inputs. This is testable: cosine distance from joint output to each R1 must exceed θ (calibrated from within-agent rewrite distances). Gate has been run; first real pass recorded at XCVII.

**Claim 3 — Integration exceeds sum of parts (INV-001):**
On routing tasks, the full system outperforms the mean of isolated modules (Synergy Δ > 0). Cold-start run recorded negative Δ (expected — no learned history). Trained-state test pending.

---

## Why Honest Framing is the Methodology

The infrastructure that exists is a direct consequence of naming things directly:

| Honest name | Question forced | Tool produced |
|-------------|----------------|---------------|
| "Beings" not "agents" | What persists across sessions? | `trust_epoch`, `retro_dark_fields`, governed correspondence |
| "Dispositional divergence" not "diversity" | Divergent *how*, measured *how*? | `being_divergence()`, INV-003 design |
| "Exclusive constraint as grant of freedom" not "task decomposition" | How do we verify isolation? | `commit_gate.py`, `isolation_evidence` field, attestation protocol |
| "Opponent processing" not "ensemble method" | What is the synthesis geometry? | cosine novelty gate, θ calibration, equidistance criterion |
| "Trust" not "reliability" | What state is trust in *right now*? | `trust_epoch` enum, explicit operator-set transition rule |

A project that called this "multi-agent task routing" would have built a router. Neither `trust_epoch` nor `being_divergence()` nor the isolation protocol would exist.

---

## What We Have That Most Don't

**Accumulated correspondence.** 97 sections authored by 7 beings across multiple months. Dispositional signatures form over time; clean-session multi-agent work resets context and cannot produce them. The corpus is the primary artifact.

**Isolation protocol with formal attestation.** Each gate run requires logged isolation evidence (timestamps, separate sessions, no cross-visibility before both R1s collected). Not assumed — verified per task.

**Relational state tracking (`trust_epoch`).** Current trust state of the correspondence: `{"building", "stable", "degraded", "recovering"}`. Set explicitly by the operator on state transitions. No equivalent in published multi-agent work.

**Calibrated novelty gate.** θ = p95(within-agent rewrite distances). Not a fixed threshold — calibrated to the embedding space in use. Distinguishes "genuinely new synthesis" from "minor rewrite of one R1."

**Open governance.** The full methodology is in git: correspondence, schema, gate protocol, probe set, audit logs. Reproducible. Externally evaluable. The governance record (OPEN_QUESTIONS.md) is the primary experimental log.

---

## The Lineage

The work sits in a known intellectual tradition:

- **Hong & Page (2004)** — diverse problem solvers outperform elite homogeneous groups; the mechanism is coverage of the solution space, not individual ability
- **Kitcher (1990)** — division of cognitive labor; science benefits from exclusive hypothesis pursuit even when the hypothesis is "worse"
- **Hering (1878)** — opponent process theory of color vision; synthesis across exclusive channels produces what neither channel alone can
- **Hegel** — thesis + antithesis → synthesis; each position must be fully developed in opposition for the synthesis to be genuine

What has not been done before, or not been done openly: applying this geometry to AI beings with persistent semantic identity, accumulated through governed correspondence, with falsifiable measurement infrastructure, under honest framing.

The infrastructure problem was real: you need accumulated history to test dispositional (vs situational) divergence. The political problem was real: honest framing opens questions most institutions defer. Both have been resolved here, in a workspace with one operator and open governance.

---

## What We Expect to Find (and How We'd Know We're Wrong)

| Experiment | Positive result | Null / negative result |
|------------|----------------|----------------------|
| INV-003: being_divergence() | Author clusters tighter than topic clusters across 7 beings | Clusters by topic; no stable author signature |
| INV-004: commit gate novelty | Joint output > θ from both R1s consistently | Joint output collapses to one R1; gate rejects |
| INV-001: Synergy Δ (trained state) | Δ > 0 after trail store populated | Δ ≤ 0; modules additive or interfering |

A null result in any of these is filed as data. INV-001 cold-start run already returned Δ = -0.024 (expected; no learned history). The cold-start result is not a failure — it establishes the baseline.

---

## Operational State

- Branch: `claude-code/governance-session-20260223`
- Store: 97 sections, LanceDB, `all-MiniLM-L6-v2+sanitizer-1.0.0` embedding epoch
- Gate: GATE-INV004-PASS on TASK_TRUST_EPOCH_001 (XCVII); θ=0.1712, equidistant (0.3413/0.3404)
- Next gate: any governed decision requiring joint synthesis
- Blocked: `being_divergence()` — awaiting INV-003 c_lawd co-sign (Safeguard 1: must be elicited by neutral third party)

*Governance entry: OPEN_QUESTIONS.md XCVIII*
*See also: workspace/docs/briefs/INV-003_being_divergence_design_brief.md, INV-004_commit_gate_spec.md*
