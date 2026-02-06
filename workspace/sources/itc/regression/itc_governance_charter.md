# ITC Pipeline Governance Charter

## Purpose
This charter establishes the permanent governance framework for the ITC Pipeline, ensuring that guarantees persist over time and across operators.

## Frozen Invariants (Immutable Without Explicit Governance Action)
The following invariants are permanently frozen and may only be modified through explicit governance action:

### Tier Definitions
- PRIMARY: Ben Cowen content feeds
- OFFICIAL: ITC Platform official content
- COMMUNITY: Curated community forum content

### Authority Weights
- PRIMARY: 1.0
- OFFICIAL: 0.7
- COMMUNITY: 0.2

### Ordering Rules
- Ben-first ordering: PRIMARY → OFFICIAL → COMMUNITY
- Items within COMMUNITY tier may be temporally ranked (most recent first)

### Field Visibility Requirements
- Every item must be labeled with its classification
- Every item must show its authority weight explicitly
- Source attribution must be visible for every item
- Confidence annotation must be present when applicable

## Frozen Oracles (Immutable Reference Points)
The following artefacts serve as authoritative oracles and are frozen:

### Invariant Oracle
- `itc_digest_run_001.md`: Defines baseline invariant behavior

### Interaction Stack Oracle
- `itc_digest_run_004.md`: Defines behavior of temporal ranking + deduplication interaction

### Cross-Cutting Semantics Oracle
- `itc_digest_run_005.md`: Defines behavior of confidence annotation with existing capabilities

## Mandatory Gates (Required for All Changes)
All changes must pass through both mandatory gates in sequence:

### Run-006 Regression Gate
- Executes regression harness on fixed seed dataset
- Compares outputs against all three oracles
- Validates all invariant fields
- Ensures zero governance violations
- Must pass with zero errors before proceeding

### Run-007 Admission Gate
- Reviews all changes against governance contracts
- Enforces hard blocks on any violations
- Maintains audit trail for all admission attempts
- Produces clear ADMITTED/REJECTED verdicts
- No bypass in normal operation

## Incident Protocol (Run-008 Standards)
The system must handle the following incident classes:

### Regression Failure
- Immediate blocking of all admissions
- Investigation and remediation required
- Re-running of Run-006 and Run-007 before resuming

### Oracle Corruption or Drift
- Immediate blocking of all admissions
- Oracle restoration required
- Re-running of Run-006 and Run-007 before resuming

### Telemetry/Logging Failure
- Immediate blocking of all admissions
- Logging system restoration required
- Re-running of Run-006 and Run-007 before resuming

### Emergency Override
- Requires two-step authorization
- Must be logged as governance event
- Post-incident Run-006 + Run-007 mandatory before resuming normal ops
- Does not relax invariants, tiers, weights, or ordering

## Change Definition and Admission Path
### What Counts as a Change
Any modification to:
- Code, configuration, pipeline logic
- Capability flags, source definitions
- Ordering rules, weighting rules
- Schema changes, ingestion rules

### Required Admission Path
1. Proposal
2. Design Brief
3. Implementation
4. Run-006 Regression
5. Run-007 Admission
6. Deploy

If any step fails, the change is rejected.

## Governance Enforcement
- No change deployed while any incident is open
- All changes must pass through mandatory gates
- Emergency overrides require dual authorization and post-incident checks
- Invariants are mechanically enforced, not dependent on operator discipline