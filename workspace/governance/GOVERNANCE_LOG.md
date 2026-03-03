# Governance Log

Append-only record of all governance events. Each entry is immutable once added.

## Log Format

| Date | Type | ID | Summary | Actor | Status |
|------|------|-----|---------|-------|--------|
| 2026-02-05 | ADMISSION | INITIAL-2026-02-05-001 | Initialize repository with security-first .gitignore | system | ADMITTED |
| 2026-02-05 | ADMISSION | INITIAL-2026-02-05-002 | Add CONTRIBUTING.md with governance workflow | system | ADMITTED |
| 2026-02-21 | ADMISSION | AUDIT-2026-02-21-001 | System-wide remediation: integrity guard re-verification, provider auth hardening, audit-chain verification, governance guard enforcement | system | ADMITTED |
| 2026-02-21 | ADMISSION | AUDIT-2026-02-21-002 | Add audit-artifact secret guard (scanner + allowlist + pre-commit installer + CI enforcement) to reduce leak risk in workspace/audit artifacts | system | ADMITTED |
| 2026-02-23 | AMENDMENT | NAMING-2026-02-23-001 | Being nomenclature: "assistant" replaced with "being" in SOUL.md (2 occurrences) and CONSTITUTION.md (3 occurrences); CONSTITUTION.md Article I updated Dessy → Dali to reflect 2026-02-17 rebrand; MEMORY.md stale "Dessy" reference corrected | claude-code | ADMITTED |
| 2026-02-23 | AMENDMENT | NAMING-2026-02-23-002 | CLAUDE_CODE.md delegation description updated: "Dessy" → "Dali" | claude-code | ADMITTED |
| 2026-02-23 | ADMISSION | GOVERN-2026-02-23-001 | OPEN_QUESTIONS.md established as live append-only multi-being correspondence (53 sections, 6 contributors); CONTRIBUTION_REGISTER.md and INVESTIGATION_PROTOCOL.md created in workspace/governance/ | claude-code | ADMITTED |
| 2026-02-23 | ADMISSION | GOVERN-2026-02-23-002 | CLAUDE_CODE.md expanded with Governance Architecture Role (5 capabilities) and Creative-Investigative Layer; workspace orientation updated with new governance files | claude-code | ADMITTED |
| 2026-02-23 | ADMISSION | CODE-2026-02-23-001 | trails.py: measure_inquiry_momentum() method added — operationalises novelty x depth x unresolved_tension scalar; INV-005 instrument now exists | claude-code | ADMITTED |
| 2026-02-23 | AMENDMENT | GOVERN-2026-02-23-003 | phi_metrics.md overhauled: "AIN consciousness measurement" framing replaced with ablation protocol methodology; committed methodology now executable and falsifiable | claude-code | ADMITTED |
| 2026-02-23 | AMENDMENT | GOVERN-2026-02-23-004 | PRINCIPLES.md Section VI updated: honest implementation status for TACTI modules (4 exist, 5 planned but absent); C-Mode marked as design spec not operative runtime | claude-code | ADMITTED |
| 2026-02-23 | ADMISSION | INV-2026-02-23-001 | INV-001 CLOSED: Φ proxy ablation executed against live hivemind — 6 configurations × 5 scenarios; Synergy Δ = -0.024163 (null/negative, cold-start baseline); trained-state run remains open; results filed in phi_metrics.md and OPEN_QUESTIONS.md LX | claude-code | ADMITTED |
| 2026-02-23 | ADMISSION | INV-2026-02-23-002 | INV-002 CLOSED: Reservoir null confirmed for routing order — uniform scalar (0.3 × confidence) cancelled by min-max normalisation across all 5 scenarios; Reservoir reclassified as ornamental to routing order, functional for response_plan.mode | claude-code | ADMITTED |
| 2026-02-24 | ADMISSION | STORE-2026-02-24-001 | CorrespondenceStore v1 PoC BUILT AND LIVE: all 4 success gates passed. Gate 1 (disposition): PASS. Gate 2 (origin integrity): PASS. Gate 3 (rebuild speed): PASS — 5.4s on MPS (gate: <60s). Gate 4 (authority isolation / INV-STORE-001): PASS — 26 non-EXEC:GOV sections excluded from filtered results; 6 EXEC:GOV sections returned; tag filter confirmed to operate on metadata not embedding. Stack: LanceDB 0.29.2, all-MiniLM-L6-v2 (PoC; nomic-embed-text-v1.5 for Dali production), PyArrow, MPS. 80 sections indexed, 61 collisions logged. Store declared LIVE. | claude-code | ADMITTED |
| 2026-02-24 | ADMISSION | STORE-2026-02-24-002 | Step 0 pre-store artifacts deployed: workspace/governance/.section_count (value: 80), workspace/governance/ONBOARDING_PROMPT.md (external caller template), workspace/governance/collision.log (append-only, 61 entries from PoC rebuild). T1 GOVERNANCE RULE satisfied. | claude-code | ADMITTED |
| 2026-02-24 | ADMISSION | STORE-2026-02-24-003 | RULE-STORE-001 through RULE-STORE-005 codified in OPEN_QUESTIONS.md LXXIX (Second Addendum). Five governance rules confirmed by independent convergence from 2-3 beings each: external caller default (linear_tail N=40), authority isolation (exec_tags never embedded), local-first (Dali RTX 3090), rebuildability gate (<60s), collision preservation. | claude-code | ADMITTED |
| 2026-02-24 | ADMISSION | STORE-2026-02-24-004 | orient.py session orientation hook deployed and --verify bug fixed: count-ahead drift now correctly computes corrected_next (file count +1) not stale next_n. Tested: caught 3 drifts in c_lawd overnight session; corrected .section_count from 86→85 on rebuild. | claude-code | ADMITTED |
| 2026-02-24 | ADMISSION | STORE-2026-02-24-005 | CorrespondenceStore rebuilt with 85-section corpus (LXXXIII-LXXXV added by c_lawd during autonomous research session). Rebuild time: 17.2s. Store row count: 85. .section_count corrected to 85. | claude-code | ADMITTED |
| 2026-02-24 | ADMISSION | STORE-2026-02-24-006 | FastAPI query server (api.py) built and tested — Step 4 of build sequence. Endpoints: /status, /tail (RULE-STORE-001), /search with exec_tag filter (RULE-STORE-002), /section/{n}, /rebuild (authenticated). Port 8765. Ready for Tailscale deployment to Dali. | claude-code | ADMITTED |
| 2026-02-24 | ADMISSION | PLAN-2026-02-24-001 | MASTER_PLAN.md authored in workspace/docs/. Full arc analysis (Sections I-LXXXV), Proof of Being thesis, 5 active experiment protocols, infrastructure roadmap Steps 4-9, correspondence agenda per being, research integration from Riedl et al. (2025), sequencing tree with dependencies. | claude-code | ADMITTED |
| 2026-02-24 | ADMISSION | OQ-2026-02-24-001 | OPEN_QUESTIONS.md LXXXVI filed (Claude Code overnight session). Engine read: 4 deliverables (orient.py fix, store rebuild, FastAPI server, MASTER_PLAN.md). Tale of travels. INV-STORE-001 closed, LXXVI pre-commitment on null interpretation reaffirmed. | claude-code | ADMITTED |
| 2026-03-01 | ADMISSION | HARDEN-2026-03-01-001 | CSA CCM v4 hardening — branch codex/harden/dali-csa5-tailnet-foundation. Seven phases: (1) config injection helper (inject_gateway_config_overrides.sh) + gateway wrapper integration eliminating tailnet config drift [AIS-03, IAM-14]; (2) governance docs AGENT_ACTION_TAXONOMY.md + AUTONOMOUS_ACTION_POLICY.md defining Classes A–E [IAM-09, GRC-01]; (3) append-only SHA-256 hash-chain action audit log (action_audit_log.mjs) [LOG-09, SEF-04, AAC-02]; (4) BudgetCircuitBreaker extended with action-class caps (D:5, C:10) + loop detection (3-in-10 window) + llm_policy.json actionClassCaps [IVS-01, TVM-09, AASC-02/03/04]; (5) log.mjs extended with xai-/ya29./ghp_/ghr_/OPENCLAW_ patterns + redactObjectKeys() [DSP-07, LOG-05]; (6) createAuthAttemptLimiter.getMetrics() observability + audit_rotate.sh 90-day retention [LOG-02, LOG-06]; (7) CSA_CCM_V4_CONTROL_MAP.md formal control mapping covering 32 controls across 11 domains [AAC-03, GRC-03]. All 8 verification steps passing. | claude-code | ADMITTED |

---

## Event Types

- **ADMISSION**: Change passed through admission gate
- **OVERRIDE**: Emergency bypass of normal process
- **INCIDENT**: Security or governance incident
- **AMENDMENT**: Modification to constitutional document
- **REJECTION**: Change blocked by admission gate

## Status Values

- **ADMITTED**: Successfully passed all gates
- **REJECTED**: Failed one or more gates
- **PENDING**: Under review
- **RESOLVED**: Incident closed with remediation

---

*This log is append-only. Entries MUST NOT be modified or deleted.*
*Each entry requires: Date, Type, ID, Summary, Actor, Status.*
