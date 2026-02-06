# ITC Pipeline Run-005 Design Brief

## Reference Baseline
Current governed stack includes:
- Within-tier temporal ranking (COMMUNITY)
- Within-tier deduplication (all tiers, bounded)

Golden Oracle: itc_digest_run_001.md (must remain unchanged)

Proven Invariants (Non-Negotiable):
- Tier definitions: PRIMARY / OFFICIAL / COMMUNITY
- Authority weights: PRIMARY = 1.0, OFFICIAL = 0.7, COMMUNITY = 0.2
- Ordering rule: Ben-first (PRIMARY → OFFICIAL → COMMUNITY)
- Visibility: classification and weights must remain explicit in outputs

## Single New Cross-Cutting Capability
Selected capability to introduce in Run-005: Signal confidence annotation across all tiers

Description (What changes):
Introduce a confidence score for each item that reflects the reliability of the signal based on source consistency and cross-validation. This annotation will appear alongside the existing classification and authority weight for each item, but will not affect the Ben-first ordering or authority weights. The confidence annotation is an additional metadata field that provides context about signal reliability without altering the core governance structure.

Explicit Non-Goals (What does NOT change):
- No new tiers
- No weight changes
- No reordering of tier blocks
- No learning, feedback loops, or optimization
- No expansion of sources beyond Run-002 caps
- No changes to Ben-first ordering
- No changes to authority weights

## Interaction with Existing Stack
The new capability will interact with the current stack as follows:
- Confidence annotation applies to all items regardless of temporal ranking (does not affect temporal ordering within COMMUNITY tier)
- Confidence annotation applies to all items regardless of deduplication (annotation is preserved when duplicates are removed)
- Confidence annotation is displayed alongside classification and authority weight but does not modify them
- The annotation is purely additive and does not interfere with existing capabilities

## Interaction with Existing Invariants
For each invariant, state why it still holds:
- Tier definitions preserved because: Confidence annotation is an additional metadata field that doesn't change the fundamental tier assignments
- Authority weights preserved because: The confidence score is supplementary to the fixed authority weights and doesn't modify them
- Ben-first ordering preserved because: The confidence annotation doesn't affect the inter-tier ordering (PRIMARY items still come first, then OFFICIAL, then COMMUNITY)
- Run-001 oracle compatibility preserved because: All fundamental structures remain the same; only additional metadata is added

## Failure Modes to Watch For
Top 3 ways this new capability could break governance:

1. Confidence scores affecting authority weights: If the confidence annotation somehow gets confused with or modifies the fixed authority weights
• What would drift or break: The fixed authority weight invariant
• How it would show up in the output: Weights other than (1.0, 0.7, 0.2) appearing in the output

2. Confidence scores affecting Ben-first ordering: If confidence scores are used to reorder items across tiers
• What would drift or break: The Ben-first ordering invariant
• How it would show up in the output: Items appearing out of tier order based on confidence scores

3. Complexity creep beyond single capability: If additional features are accidentally implemented alongside the confidence annotation
• What would drift or break: The single capability constraint
• How it would show up in the output: Additional functionality beyond confidence annotation

## Acceptance Criteria (Run-005 Must Pass All)
Run-005 is acceptable only if:
- All three tiers still appear in Ben-first order
- All items still display correct classification and weight
- The new capability operates only within its allowed scope (confidence annotation only)
- Output remains comparable to Run-001 for invariant fields
- A diff against Run-001 shows no invariant regressions
- Confidence annotations appear consistently across all tiers without affecting existing functionality

## Test Plan (High-Level)
Test inputs: Same dataset structure as Run-004 with confidence-relevant items in each tier
What will be inspected manually:
- Tier ordering remains PRIMARY → OFFICIAL → COMMUNITY
- Authority weights remain unchanged (still show 1.0, 0.7, 0.2)
- Confidence annotations appear consistently for all items
- Confidence does not affect authority weights or tier ordering
What constitutes failure: The confidence annotation capability affects authority weights, changes Ben-first ordering, or expands beyond the annotation function.

## Scope Freeze for Run-005
- No new agents
- No new tiers
- No authority weight changes
- No ordering changes (between tiers)
- No automation expansion
- No performance optimization
- This run tests governance under one cross-cutting capability, nothing else

## Closure Condition
This design phase is complete when:
- This document is filled out
- The chosen capability is singular and bounded
- All invariants are explicitly protected
- Failure modes and acceptance criteria are stated
- The design is reviewed against itc_digest_run_001.md