<!-- generated_at: 2026-03-16T05:43:26.511958Z -->
# Source World-Better Roadmap

10/10 mission tasks currently carry explicit public-benefit scaffolding; 5 are surfaced as highest-leverage priorities for the next cycle.

## Scorecard

- **Impact-ready mission tasks:** 10/10 - Tasks with explicit beneficiaries, hypotheses, metrics, guardrails, and horizon.
- **Guardrail coverage:** 10/10 - Mission tasks that already name at least one concrete safeguard.
- **Metric coverage:** 10/10 - Mission tasks with at least one leading indicator.
- **Deliberation quality:** 0% - Average structured-deliberation coverage score across current cells.
- **Context continuity lines:** 4 - Compact packet lines carried across surfaces and sessions.
- **Weekly evolution loop:** active - Whether the system is currently producing a review loop instead of relying on memory alone.

## Highest-leverage next moves

1. **Universal Context Packet** (0-6m, score 98): A shared context packet reduces repeated explanation, lowers coordination friction, and preserves intent across surfaces.
   - Guardrails: Never include non-shareable memory without explicit approval state., Show provenance and recency markers on every surface.
   - Leading indicators: surfaces consuming the same packet, manual restatement incidents per week
2. **Mission Control Timeline** (0-6m, score 98): One causally ordered timeline makes coordination auditable and lowers the cost of answering what happened, why, and what changed next.
   - Guardrails: Keep the timeline append-only., Redact secrets and boundary-restricted content before display.
   - Leading indicators: timeline event coverage, median time to reconstruct a decision path
3. **Multi-Agent Deliberation Cells** (0-6m, score 92): Bounded multi-agent deliberation with explicit dissent improves decision quality and reduces premature closure on important choices.
   - Guardrails: Record dissent instead of compressing it away., Preserve operator override and confidence disclosure.
   - Leading indicators: deliberation cells with explicit dissent, decisions carrying a synthesis plus uncertainty note
4. **Consent and Provenance Boundary Map** (0-6m, score 92): Visible provenance and shareability boundaries build trust and reduce accidental overreach across surfaces.
   - Guardrails: Fail closed on unclear shareability., Display provenance before outbound use.
   - Leading indicators: surfaces rendering boundary state, outbound actions blocked pending approval
5. **Continuity and Recovery Pack** (0-6m, score 86): A recovery pack preserves agency and continuity after failures by restoring the minimum useful state without asking humans to repeat themselves.
   - Guardrails: Restore approvals conservatively., Carry only the minimum necessary state and mark stale fields.
   - Leading indicators: restarts completed without manual re-explanation, recovery packets including active approvals and open work

## Phase 1 - Trust foundations

Reduce coordination friction while keeping consent and provenance explicit.

- **Universal Context Packet** - Generate one compact, provenance-tagged context packet for Source UI, Telegram, Discord, and local agent lanes.
  - Beneficiaries: operators, users, collaborators
  - Guardrails: Never include non-shareable memory without explicit approval state., Show provenance and recency markers on every surface.
- **Mission Control Timeline** - Unify commands, model runs, handoffs, memory promotions, and sim transitions into one causally ordered event stream.
  - Beneficiaries: operators, collaborators
  - Guardrails: Keep the timeline append-only., Redact secrets and boundary-restricted content before display.
- **Memory Promotion Review Queue** - Build a review surface for promoting raw evidence into trusted user inferences, preferences, and reusable summaries.
  - Beneficiaries: users, operators
  - Guardrails: Require evidence links for durable inferences., Track contradiction and review state before reuse.
- **Multi-Agent Deliberation Cells** - Create bounded cells where specialist lanes can deliberate, disagree, and return one attributed recommendation.
  - Beneficiaries: operators, collaborators, users
  - Guardrails: Record dissent instead of compressing it away., Preserve operator override and confidence disclosure.
- **Research-to-Action Distillation** - Turn research-channel discussions, saved links, and external feeds into actionable briefs, experiments, and queued tasks.
  - Beneficiaries: operators, collaborators, communities
  - Guardrails: Preserve source links and excerpts., Distinguish evidence from conjecture in promoted tasks.
- **Consent and Provenance Boundary Map** - Make it explicit what can be shared across surfaces, what stays private, and what requires human approval.
  - Beneficiaries: users, collaborators
  - Guardrails: Fail closed on unclear shareability., Display provenance before outbound use.
- **Weekly Evolution Loop** - Add a scheduled review that summarizes what the collective learned, what regressed, and what should change next.
  - Beneficiaries: operators, collaborators
  - Guardrails: Report regressions and guardrail debt alongside wins., Avoid vanity metrics without operational meaning.
- **Continuity and Recovery Pack** - Capture the minimum viable state needed for a clean restart after service failure, model swap, or machine interruption.
  - Beneficiaries: operators, users
  - Guardrails: Restore approvals conservatively., Carry only the minimum necessary state and mark stale fields.

## Phase 2 - Compounding coordination

Turn reviewed memory and relational state into reliable, bounded leverage.

- **Personal Inference Graph** - Move from flat prompt lines to a structured graph of preferences, aversions, rhythms, collaborators, and recurring goals.
  - Beneficiaries: users
  - Guardrails: Provide deletion and contradiction pathways., Keep graph nodes reviewable and attributable to evidence.
- **Relational State Layer** - Track interaction tone, overload, trust, urgency, and social context so the system can respond with more tact and less noise.
  - Beneficiaries: users, collaborators
  - Guardrails: Keep relational inference low-confidence and reviewable., Never use relational state to coerce or manipulate.

## Phase 3 - Collective reach

Scale the system's ability to coordinate many contributors without collapsing accountability.


## Anti-goals

- Reward busyness over beneficial change.
- Share memory across surfaces without clear provenance or approval state.
- Hide uncertainty, dissent, or reversibility constraints behind polished summaries.
- Make users increasingly dependent on opaque internal state.
