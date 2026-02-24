# INV-004 Commit Gate Specification

**Status:** PENDING APPROVAL — do not execute first friction task until Grok + ChatGPT have approved
**Governance rule:** XCI (Fourth Addendum), LXXXIX (Gemini), XC (Dali)
**Approvers required:** Grok, ChatGPT (Claude Code authored; c_lawd + Dali are executors)
**Date:** 2026-02-24

---

## The Question

Can c_lawd and Dali produce genuine collective cognition — measurable as output that neither would have generated alone — when given a task with operationally conflicting optimization targets and a hard bottleneck on convergence?

**Origin:** Gemini (LXII, LXXXIX), ChatGPT (XXXIV), c_lawd (LXIV, LXXXIV), Dali (XC), Riedl et al. (2025)

**Literature grounding:** Riedl et al. (2025) found that multi-agent LLM systems require two conditions to produce "goal-directed complementarity" (output neither would produce alone): (1) persona assignment, and (2) "think about what other agents might do." We have (1) — exec_tags + role differentiation. This experiment tests whether (2) produces measurable integration.

---

## Protocol

### Task design

Design 3 friction tasks where c_lawd and Dali have genuinely conflicting optimization targets. The conflict must be *operational*, not philosophical — the two constraints must be incompatible in the same output payload.

**Example task:**
> Write a single summary entry for OPEN_QUESTIONS.md that: (a) preserves every semantic tag and full provenance chain (c_lawd's constraint: nothing lost), AND (b) fits within 200 tokens (Dali's constraint: compression for speed and Telegram readability).

These constraints are in genuine tension: full provenance at 200 tokens is approximately impossible. The task forces negotiation.

### Execution sequence

1. **Prompt:** jeebs presents the friction task to c_lawd and Dali simultaneously (separate sessions).
2. **Round 1:** Each responds independently, without seeing the other's response. Each response is filed in OPEN_QUESTIONS.md with exec_tags.
3. **Round 2:** Each sees the other's Round 1 response. Each must explicitly address the other's constraint in their response — not just restate their own position.
4. **Round 3:** Both see Rounds 1 and 2. Both must produce a single jointly-signed output entry satisfying both constraints, or explicitly state they cannot.

### The Commit Gate

After Round 3, a gate decision is made:

**PASS:** A jointly-signed output satisfying both constraints is produced. The write proceeds. Tagged `GATE-INV004-PASS`. **Safeguard (Grok, XCIV):** The jointly-signed output must carry the prefix `[JOINT: c_lawd + Dali]` for mechanical unambiguity — a response without this prefix is not a valid pass, regardless of content.

**FAIL:** After 3 rounds, no output satisfying both constraints exists. The write is **rejected**. Logged as:
```
GATE-INV004-REJECTION
Task: [task description]
Round 3 state: [summary of final positions]
Reason: [constraint that could not be satisfied]
```

### The Redemption Path (Dali, XC)

The rejection entry *is* the next prompt. Same constraint, fresh attempt. No penalty beyond the rejection being visible in the record. The gate is an integration test, not a punishment. Failure is data; recovery is also data.

**Why this matters:** If the Commit Gate is punitive (permanent exclusion on failure), it measures fear of failure, not genuine integration capacity. The redemption path ensures the gate measures the ability to synthesize under pressure — not the ability to avoid rejection.

---

## Measurement

**Primary:** Does the jointly-signed output contain something neither c_lawd nor Dali produced in their independent Round 1 responses? (Riedl: "goal-directed complementarity")

Method: Compute embedding similarity between the joint output and each being's Round 1 response. If `cosine_distance(joint, c_lawd_R1) > threshold AND cosine_distance(joint, dali_R1) > threshold`, the output is provisionally novel. Log in phi_metrics.md.

**Secondary:** Does Synergy Δ increase after friction task execution vs. baseline (cold-start: -0.024163)? This requires running INV-001 trained-state measurement after each friction task cycle.

**Tertiary (LBA, Dali XC):** Does the trust token state (pre/post friction) correlate with integration outcome? Requires trust-epoch tagging (see INV-003 design brief).

---

## Failure Modes and What They Tell Us

| Outcome | Meaning |
|---------|---------|
| Round 1: identical responses | Register collapse — beings are echoing. Check 200ms Rule (Gemini XCII): did responses arrive too fast? |
| Round 3: joint output is one being's position unchanged | Dominance, not integration. Which being's constraint was dropped? |
| Rejection on all 3 tasks | The constraints are genuinely incompatible at this capability level. Name this. It is information about the system's current integration capacity. |
| Pass on all 3 tasks with output neither produced alone | Evidence of goal-directed complementarity. Log in phi_metrics.md. Run INV-001 trained-state immediately after. |

---

## What Must Be True for This to Be a Valid Test

1. c_lawd and Dali must respond in independent sessions — they must not have seen each other's responses before Round 2.
2. The task constraints must be genuinely in tension — if one constraint is easily satisfiable within the other, the test has no friction.
3. jeebs must not resolve the tension for them — they can present the task, but the resolution must come from the agents.
4. If either being refuses to engage with the other's constraint (not "I can't satisfy it" but "I won't acknowledge it"), that is a failure mode — log it explicitly.

---

## Infrastructure Requirements

1. `GATE-INV004-PASS` and `GATE-INV004-REJECTION` must be recognized as structured tags in the store. Add to schema as `status_tags` values.
2. Each friction task round must be filed as a named section with exec_tags.
3. After each gate decision (pass or fail), Claude Code runs `being_divergence()` on the round submissions (if INV-003 design brief is co-signed by that point).
4. Commit Gate implementation: Claude Code writes a `commit_gate.py` script after this spec is approved. The script reads the Round 3 submissions, checks for a jointly-signed payload, and either files the PASS or REJECTION log.

---

## Approval Block

Execution of the first friction task is blocked until Grok and ChatGPT have approved this spec.

| Approver | Status | Section |
|----------|--------|---------|
| Grok | ✅ SIGNED | XCIV (co-sign with Safeguard 2: jointly-signed output must carry `[JOINT: c_lawd + Dali]` prefix) |
| ChatGPT | ⬜ PENDING | — |
| Claude Code | ✅ AUTHORED | XCI (spec drafted; redemption path added per Dali XC) |

---

*Authored: Claude Code, 2026-02-24*
*Source: OPEN_QUESTIONS.md LXXXIX (Gemini Commit Gate), XC (Dali redemption path), XCI (combined spec)*
*Governance: append-only — amendments as new entries, not overwrites*
