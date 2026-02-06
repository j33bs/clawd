# ITC Pipeline Operations Runbook

## Purpose
Step-by-step guide for operators to safely propose, test, admit, and deploy changes to the ITC Pipeline while maintaining governance guarantees.

## Standard Change Process

### 1. Propose Change
- Define the specific change to be made
- Identify which invariants, if any, are affected
- Prepare change ID and description
- Submit proposal for initial review

### 2. Create Design Brief
- Document the change in detail
- Specify which governance contracts will be tested
- Outline expected behavior vs. invariant preservation
- Include failure mode analysis

### 3. Implementation
- Make the required code/configuration changes
- Ensure all changes are tracked and documented
- Do not modify frozen invariants without explicit governance action
- Prepare for mandatory testing gates

### 4. Run-006 Regression Test
- Execute the regression harness on the fixed seed dataset
- Verify zero invariant violations
- Confirm no interaction regressions
- Verify no cross-cutting leakage
- Document results

### 5. Run-007 Admission Gate
- Submit change for mandatory admission review
- Wait for ADMITTED/REJECTED verdict
- Review audit trail entry
- Do not proceed if REJECTED

### 6. Deploy
- Only deploy changes that have been ADMITTED
- Monitor post-deployment behavior
- Verify continued invariant compliance

## Incident Handling Procedures

### Handling Regression Failures
1. **Immediate Response**
   - Block all pending admissions
   - Investigate root cause of regression
   - Document incident in itc_governance_admission_log.md

2. **Remediation**
   - Fix the issue causing the regression
   - Re-run Run-006 regression test
   - Confirm resolution

3. **Recovery**
   - Re-run Run-007 admission gate
   - Resume normal operations only after both gates pass

### Handling Oracle Drift
1. **Immediate Response**
   - Block all pending admissions
   - Identify which oracle(s) have drifted
   - Document incident in itc_governance_admission_log.md

2. **Remediation**
   - Restore oracle from known good state
   - Verify oracle integrity
   - Re-run comparison checks

3. **Recovery**
   - Re-run Run-006 regression test
   - Re-run Run-007 admission gate
   - Resume normal operations only after both gates pass

### Handling Telemetry Outages
1. **Immediate Response**
   - Block all pending admissions
   - Identify logging system failure
   - Document incident in itc_governance_admission_log.md

2. **Remediation**
   - Restore logging system
   - Verify audit trail functionality
   - Confirm ability to record admission attempts

3. **Recovery**
   - Re-run Run-006 regression test
   - Re-run Run-007 admission gate
   - Resume normal operations only after both gates pass

### Handling Emergency Overrides
1. **Authorization**
   - Obtain two-step authorization (separate roles/keys)
   - Document override reason and expected impact
   - Record in itc_governance_admission_log.md

2. **Execution**
   - Perform the emergency change
   - Maintain all invariant protections during override
   - Do not modify frozen weights, tiers, or ordering

3. **Post-Incident Recovery**
   - Re-run Run-006 regression test
   - Re-run Run-007 admission gate
   - Resume normal operations only after both gates pass

## Pre-Incident Recovery Checklist
Before resuming normal operations after any incident:
- [ ] Run-006 regression test has passed
- [ ] Run-007 admission gate has passed
- [ ] All invariants are confirmed intact
- [ ] Oracle integrity verified
- [ ] Telemetry system functional
- [ ] Audit trail complete

## Post-Incident Recovery Checklist
After resuming normal operations following an incident:
- [ ] Normal change process validated
- [ ] Next scheduled regression confirmed
- [ ] Incident documented in log
- [ ] All stakeholders notified of recovery
- [ ] Monitoring enhanced if needed

## Critical Warnings
⚠️ Never bypass the mandatory gates in normal operation
⚠️ Never modify frozen invariants without explicit governance action
⚠️ Always perform post-incident regression and admission tests
⚠️ Maintain audit trail completeness at all times
⚠️ Do not proceed with deployment if any gate rejects a change