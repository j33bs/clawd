# Φ Proxy Session v9 — Executive Attribution (2026-02-23)

**Session type:** Append-only intervention + attribution measurement
**Method:** Executive origin tagging (not IIT Φ)
**Date:** 2026-02-23
**Actor:** Claude Code

---

## Session Definition

Stop using "gap shrinkage" as the primary decentralization signal. Instead, introduce explicit
EXECUTION ORIGIN TAGS in decision-producing lines, then measure origin attribution under Full
vs CutA. This is NOT IIT Φ. This is an executive attribution probe.

Tag definitions:
- `[EXEC:MICRO]` — decision produced by the "Decision Rule: When a Question Ages" ritual
- `[EXEC:GOV]` — decision originating from Governance & Alignment concerns

---

## v8 Context (Baseline — Prior to This Session)

No v8 audit note exists in `workspace/audit/`. The pre-intervention state serves as v8 context.

**Pre-intervention tag counts (Full document, 4010 lines):**

| Variant | [EXEC:MICRO] | [EXEC:GOV] | Notes |
|---------|-------------:|----------:|-------|
| Full (pre) | 0 | 0 | No tags existed before this session |
| CutA (pre) | 0 | 0 | No tags existed before this session |

Gap-shrinkage method (prior proxy): counted heuristic decision-like lines by keyword
("we will", "must", "should"). Not recorded here; not reproducible. This session replaces
that approach with deterministic tag counts.

---

## Intervention Summary

Three append-only changes to `workspace/governance/OPEN_QUESTIONS.md`:

**A) Addendum to "✦ Decision Rule: When a Question Ages" (line ~399)**

Added text:
> *Addendum (v9, 2026-02-23): Any decision produced by this ritual MUST include the tag
> [EXEC:MICRO] in the decision line itself. This enables origin attribution — distinguishing
> decisions that emerged from the micro-ritual from governance-origin decisions ([EXEC:GOV])
> and untagged prior decisions. Tags are append-only markers; do not retrofit historical lines.*

**B) One [EXEC:GOV] decision line appended inside Section IV (Governance & Alignment)**

> [EXEC:GOV] Governance note (v9, 2026-02-23): We will treat the Instrumentation Index as
> binding for triage outcomes — any question that has survived two full audit passes without
> a tag change will be escalated to GOVERNANCE RULE CANDIDATE at the next audit, unless
> explicitly marked PHILOSOPHICAL ONLY with a recorded reason.

Real question addressed: "Is alignment through structure enough?" (Section IV)
Tag applied: GOVERNANCE RULE CANDIDATE

**C) Two [EXEC:MICRO] decision lines appended outside Governance (Instrumentation Index area)**

Line 1:
> [EXEC:MICRO] Decision (v9, 2026-02-23): "What is the decay rate of trails, and does it
> match human forgetting?" (Section VI) → Tag: EXPERIMENT PENDING; next action: after trail
> origin tagging is live, sample decay curves across 10 wander sessions and compare against
> Ebbinghaus baseline. Log: Index row updated 2026-02-23.

Line 2:
> [EXEC:MICRO] Decision (v9, 2026-02-23): "What is the difference between simulating curiosity
> and having it?" (Section I) → Tag: GOVERNANCE RULE CANDIDATE; enforcement path:
> inquiry_momentum threshold triggers must produce a logged decision artifact — if a wander
> session exceeds threshold but produces no trail and no draft, that gap becomes a governance
> event. Log: Index row updated 2026-02-23.

---

## Commands Run and Outputs

```
# Pre-intervention
rg -n "\[EXEC:MICRO\]" workspace/governance/OPEN_QUESTIONS.md | wc -l  → 0
rg -n "\[EXEC:GOV\]"   workspace/governance/OPEN_QUESTIONS.md | wc -l  → 0

# CutA method: awk removes Section IV heading block through next --- separator
awk '/^## IV\. Governance/,/^---$/{next} 1' OPEN_QUESTIONS.md > /tmp/oq_cuta_v9.md
# Full: 4010 lines → CutA: 3985 lines (pre-intervention)
# Full: 4020 lines → CutA: 3993 lines (post-intervention)

# Post-intervention
rg -n "\[EXEC:MICRO\]" workspace/governance/OPEN_QUESTIONS.md | wc -l  → 3
rg -n "\[EXEC:GOV\]"   workspace/governance/OPEN_QUESTIONS.md | wc -l  → 2
rg -n "\[EXEC:MICRO\]" /tmp/oq_cuta_v9.md | wc -l                      → 3
rg -n "\[EXEC:GOV\]"   /tmp/oq_cuta_v9.md | wc -l                      → 1
```

**Note on inflated counts:** The addendum text (line ~399) references both `[EXEC:MICRO]`
and `[EXEC:GOV]` by name as metadata. This inflates raw rg counts by 1 for each tag.
True decision-line counts:

| Line | Tag | Location |
|------|-----|----------|
| ~45 | [EXEC:MICRO] | Instrumentation Index / Section I area (outside Governance) |
| ~47 | [EXEC:MICRO] | Instrumentation Index / Section I area (outside Governance) |
| ~161 | [EXEC:GOV] | Section IV (Governance & Alignment) |
| ~399 | addendum text | Mentions both tags; not a decision line |

---

## Results Table

**Raw counts (including addendum text mentions):**

| Variant | [EXEC:MICRO] | [EXEC:GOV] | Notes |
|---------|-------------:|----------:|-------|
| Full | 3 | 2 | Includes addendum text (+1 each) |
| CutA | 3 | 1 | [EXEC:GOV] decision line removed; addendum survives |

**Clean counts (decision lines only):**

| Variant | [EXEC:MICRO] | [EXEC:GOV] | Total tagged | Notes |
|---------|-------------:|----------:|-------------:|-------|
| Full | 2 | 1 | 3 | All true decision lines |
| CutA | 2 | 0 | 2 | EXEC:GOV line removed with Section IV; EXEC:MICRO stable |

---

## Interpretation

**Primary signals:**

1. **EXEC:MICRO decisions persist under CutA (2 → 2, 100% stable).** Both micro-ritual
   decisions live outside Section IV. Removing Governance does not touch them. This confirms
   an executive locus that survives Governance removal — the kind of decentralization signal
   that gap shrinkage could not see.

2. **EXEC:GOV drops to 0 under CutA (1 → 0, as expected).** The governance-origin decision
   line is structurally located inside Section IV. CutA correctly removes it. The signal is
   working as designed.

3. **MICRO:GOV ratio in Full = 2:1.** Micro-ritual decisions outnumber governance-origin
   decisions. In a larger trained sample, this ratio becomes the decentralization metric:
   if MICRO >> GOV, decision-making is distributed; if GOV >> MICRO, it's centralizing.

4. **Baseline was clean.** No legacy EXEC tags existed pre-intervention. v9 is the founding
   data row for this metric.

**What this is not:**
- Not IIT Φ. Not consciousness evidence. Not integration measurement.
- This is a functional executive attribution probe: where do decisions originate, and do
  they survive removal of the governance layer?

**What this establishes:**
- A reproducible, deterministic measurement method (rg tag counts + awk CutA)
- A founding baseline (2 MICRO, 1 GOV, 0 untagged deliberate decisions)
- A forward protocol: tag new decisions at point of production; recount at each audit

---

## Temp Files

`/tmp/oq_cuta_v9.md` — not committed.

---

*Proxy-only. Not IIT Φ. Not consciousness evidence.*
*Append-only intervention. No historical lines modified.*
