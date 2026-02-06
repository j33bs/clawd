# ITC Pipeline — Run-003 Design Brief

## 1. Reference Baseline
Golden Oracle:
• itc_digest_run_001.md (must remain unchanged)

Proven Invariants (Non-Negotiable):
• Tier definitions: PRIMARY / OFFICIAL / COMMUNITY
• Authority weights:
• PRIMARY = 1.0
• OFFICIAL = 0.7
• COMMUNITY = 0.2
• Ordering rule: Ben-first (PRIMARY → OFFICIAL → COMMUNITY)
• Visibility: classification and weights must remain explicit in outputs

## 2. Single New Capability (Choose Exactly One)
Selected capability to introduce in Run-003: Simple ranking heuristic within COMMUNITY tier based on temporal recency

Description (What changes):
Implement a temporal decay factor for content relevance in the COMMUNITY tier. This will rank more recent community contributions higher than older ones within the community section, while maintaining the core authority-based weighting system and overall Ben-first ordering. The temporal factor only affects relative ranking within the COMMUNITY section, not the absolute authority weights.

Explicit Non-Goals (What does NOT change):
• No new tiers
• No weight changes
• No reordering of tier blocks
• No learning, feedback loops, or optimization
• No expansion of sources beyond Run-002

## 3. Interaction with Existing Invariants
For each invariant, state why it still holds:
• Tier definitions preserved because: The temporal ranking only affects ordering within the COMMUNITY tier, not the tier definitions themselves
• Authority weights preserved because: The temporal factor does not change the assigned weights (1.0, 0.7, 0.2), only the ordering within the COMMUNITY section
• Ben-first ordering preserved because: Temporal factors only affect relative ordering within each tier, not the inter-tier ordering (PRIMARY items still come first, then OFFICIAL, then COMMUNITY)
• Run-001 oracle compatibility preserved because: All fundamental structures and weight assignments remain the same, only internal ordering within COMMUNITY section may change

## 4. Failure Modes to Watch For
List the top 3 ways this new capability could break governance:

1. Temporal ranking overriding authority-based ordering: If the temporal factor somehow affects inter-tier ordering and allows COMMUNITY items to appear before PRIMARY or OFFICIAL items
• What would drift or break: The Ben-first ordering invariant
• How it would show up in the output: COMMUNITY items appearing before PRIMARY or OFFICIAL sections

2. Temporal factors affecting weights: If the temporal decay somehow modifies the explicit authority weights instead of just affecting internal ordering
• What would drift or break: The fixed authority weight invariant
• How it would show up in the output: Weights other than (1.0, 0.7, 0.2) appearing in the output

3. Complexity creep beyond single capability: If additional features are accidentally implemented alongside the temporal ranking
• What would drift or break: The single capability constraint
• How it would show up in the output: Additional functionality beyond temporal ranking within COMMUNITY tier

## 5. Acceptance Criteria (Run-003 Must Pass All)
Run-003 is acceptable only if:
• All three tiers still appear in Ben-first order
• All items still display correct classification and weight
• The new capability operates only within its allowed scope (ranking within COMMUNITY tier only)
• Output remains comparable to Run-001 for invariant fields
• A diff against Run-001 shows no invariant regressions

## 6. Test Plan (High-Level)
Test inputs: Same dataset structure as Run-002 with time-stamped items in each tier
What will be inspected manually:
• Tier ordering remains PRIMARY → OFFICIAL → COMMUNITY
• Authority weights remain unchanged (still show 1.0, 0.7, 0.2)
• Within COMMUNITY tier, temporal ordering is applied correctly
What constitutes failure: The temporal ranking capability affects inter-tier ordering, changes authority weights, or expands beyond the COMMUNITY tier.

## 7. Scope Freeze for Run-003
• No new agents
• No new tiers
• No authority weight changes
• No ordering changes (between tiers)
• No automation expansion
• No performance optimization
• This run tests governance under one added complexity, nothing else

## 8. Closure Condition
This design phase is complete when:
• This document is filled out
• The chosen capability is singular and bounded
• All invariants are explicitly protected
• Failure modes and acceptance criteria are stated
• The design is reviewed against itc_digest_run_001.md