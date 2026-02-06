# ITC Pipeline Run-006 Design Brief: Governance Regression Harness

## Purpose
Prove that future changes cannot silently break:
• Tier semantics
• Authority weights
• Ben-first ordering
• Field visibility
• The governed stack behavior

## What Run-006 Introduces (Design-First)
A regression check mode that:
• Replays a fixed seed dataset
• Compares outputs against:
• itc_digest_run_001.md (invariants)
• itc_digest_run_004.md (interaction stack)
• itc_digest_run_005.md (cross-cutting semantics)
• Fails hard on any invariant or contract violation

## Fixed Seed Dataset
The regression harness will use a predetermined set of 12 items (4 per tier) that have been validated across all previous runs:
- 4 PRIMARY items (Ben Cowen content)
- 4 OFFICIAL items (ITC Platform content)
- 4 COMMUNITY items (Community forum content)

These items will be identical across all regression runs to ensure consistency.

## Comparison Protocol
The harness will perform the following comparisons:
1. Against itc_digest_run_001.md:
   - Verify tier definitions remain PRIMARY/OFFICIAL/COMMUNITY
   - Verify authority weights remain 1.0/0.7/0.2
   - Verify Ben-first ordering (PRIMARY → OFFICIAL → COMMUNITY)
   - Verify field visibility and structure

2. Against itc_digest_run_004.md:
   - Verify temporal ranking behavior within COMMUNITY tier
   - Verify deduplication behavior within tiers
   - Verify interaction rules between capabilities

3. Against itc_digest_run_005.md:
   - Verify confidence annotation presence and behavior
   - Verify that confidence annotation does not affect other capabilities
   - Verify all previous functionality remains intact

## Failure Modes
The regression harness will fail hard if:
1. Tier semantics change (different tier labels or meanings)
2. Authority weights change (values other than 1.0/0.7/0.2)
3. Ben-first ordering is violated (incorrect inter-tier ordering)
4. Required fields are missing or changed in structure
5. Previously functioning capabilities (temporal ranking, deduplication, confidence annotation) are broken
6. Interaction rules between capabilities are violated

## Output Contract
The regression harness will produce:
- itc_digest_run_006_regression_report.md
- Detailed comparison results showing any deviations
- Pass/fail status for each comparison target
- Specific invariant violations if any are detected

## Hard Fail Protocol
If any invariant or contract violation is detected:
- Immediately halt the run
- Generate a detailed error report
- Do not produce a standard digest output
- Log the violation for review

## Purpose Completion
This completes the system transformation from "we can evolve safely" to "we cannot accidentally evolve unsafely" by providing an automated check that prevents silent regressions of core governance properties.