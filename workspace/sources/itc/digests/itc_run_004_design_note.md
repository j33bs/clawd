# ITC Pipeline Run-004 Design Note

## Purpose
Design Run-004 to combine two bounded capabilities while maintaining all invariants.

## Capabilities to Combine
Capability A: Within-tier temporal ranking in COMMUNITY (from Run-003)
Capability B: Basic deduplication within tiers to remove redundant content

## Interaction Rule
Temporal ranking applies first, then deduplication removes redundant items based on content similarity, preserving the most recent version of any duplicated content within each tier.