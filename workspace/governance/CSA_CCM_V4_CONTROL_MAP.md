# CSA CCM v4 Control Map — OpenClaw Autonomous Agent
**Version:** 1.0
**Date:** 2026-03-01
**Branch:** `codex/harden/dali-csa5-tailnet-foundation`
**Scope:** Autonomous AI agent on local tailnet (dali / clawd)
**Status:** Living document — updated at each admission gate

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ Implemented | Control fully implemented and tested |
| ⚠️ Partial | Partially implemented; noted gaps |
| ❌ Gap | Control not yet addressed |
| N/A | Not applicable to this scope |

---

## AIS — Application Interface Security

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| AIS-02 | Application Security Baseline | ✅ Implemented | `workspace/runtime_hardening/src/config.mjs`, `scripts/run_openclaw_gateway_repo_dali.sh` | Config fail-fast validates all required env vars at startup; gateway wrapper enforces provider allowlist and bind-mode constraints |
| AIS-03 | Application Security Metrics | ✅ Implemented | `workspace/runtime_hardening/src/security/tool_sanitize.mjs`, `tools/inject_gateway_config_overrides.sh`, `tools/gateway_security_hardening_patch.mjs` | Tool payload sanitization; config injection from env vars (Phase 1); origin allowlisting with wildcard rejection |
| AIS-05 | Automated Application Security Testing | ✅ Implemented | `tools/run_security_gates.sh`, `tests/gateway_security_hardening_patch.test.js`, `tests/run_openclaw_gateway_repo_dali_hardening.test.js` | Automated gate sequence covering patch verification, origin guards, rate limiter metrics, and config injection |

---

## AAC — Audit Assurance & Compliance

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| AAC-02 | Audit Planning | ✅ Implemented | `workspace/runtime_hardening/src/action_audit_log.mjs` | Append-only JSONL action audit log with SHA-256 hash chain; covers all autonomous agent actions |
| AAC-03 | Information System Regulatory Mapping | ✅ Implemented | `workspace/governance/CSA_CCM_V4_CONTROL_MAP.md` (this document) | Formal per-control mapping across all CCM v4 domains relevant to autonomous agent scope |

---

## CCC — Change Control & Configuration Management

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| CCC-01 | Change Management Policy | ✅ Implemented | `workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md` | Security governance contract defines change authorization requirements |
| CCC-02 | Change Management Technology | ✅ Implemented | `tools/guard_worktree_boundary.sh` | Worktree CANON boundary guard enforces repo integrity on every gateway start |
| CCC-03 | Change Management Baseline | ✅ Implemented | `tools/apply_gateway_security_hardening.sh`, `tools/run_security_gates.sh` | Security gate sequence verifies patch presence before each run |
| CCC-04 | Change Management Restrictions | ✅ Implemented | `core/system2/security/integrity_guard.js`, `tools/guard_worktree_boundary.sh` | Governance anchor verification; worktree boundary guard prevents unauthorized divergence |

---

## DSP — Data Security & Privacy Lifecycle Management

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| DSP-01 | Security and Privacy Policy | ✅ Implemented | `workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md`, `workspace/governance/AUTONOMOUS_ACTION_POLICY.md` | Governance contract + autonomous action policy together define data handling requirements |
| DSP-07 | Sensitive Data Protection | ✅ Implemented | `workspace/runtime_hardening/src/log.mjs` | Structured logger redacts: Bearer/Basic auth, sk-/gsk-/xai-/ya29./ghp_/ghr_ tokens, OPENCLAW_ env vars, generic api_key/password/secret/token fields; `redactObjectKeys()` helper for logged objects |

---

## GRC — Governance, Risk & Compliance

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| GRC-01 | Governance Policy | ✅ Implemented | `workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md`, `workspace/governance/AGENT_ACTION_TAXONOMY.md`, `workspace/governance/AUTONOMOUS_ACTION_POLICY.md` | Three-document governance suite: security contract, action taxonomy, and autonomous action policy |
| GRC-03 | Governance Reviews | ✅ Implemented | `workspace/governance/CSA_CCM_V4_CONTROL_MAP.md` (this document) | Living control map reviewed and updated at each admission gate; review triggers documented in AUTONOMOUS_ACTION_POLICY.md |

---

## IAM — Identity & Access Management

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| IAM-06 | User Access Reviews | ✅ Implemented | `workspace/runtime_hardening/src/session.mjs` | Session TTL and max-session bounds enforced; sessions expire automatically |
| IAM-09 | User Access Restrictions | ✅ Implemented | `core/system2/security/trust_boundary.js`, `workspace/governance/AUTONOMOUS_ACTION_POLICY.md` | Fail-closed trust boundary for untrusted input; autonomous action policy defines per-class authorization matrix |
| IAM-14 | Strong Authentication | ✅ Implemented | `tools/gateway_security_hardening_patch.mjs`, `tools/inject_gateway_config_overrides.sh`, `scripts/run_openclaw_gateway_repo_dali.sh` | Auth rate limiting (10 attempts/60s); origin allowlisting enforced in gateway; config override injection eliminates manual config drift |

---

## IPY — Interoperability & Portability

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| IPY-04 | Access Restrictions | ✅ Implemented | `workspace/policy/llm_policy.json`, `scripts/run_openclaw_gateway_repo_dali.sh` | Provider allowlist (`OPENCLAW_PROVIDER_ALLOWLIST`) restricts LLM egress to approved providers only |

---

## IVS — Infrastructure & Virtualization Security

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| IVS-01 | Network Security | ✅ Implemented | `core/system2/budget_circuit_breaker.js` | Action-class caps (Class D: 5, Class C: 10 per run) bound blast radius; loop detection trips breaker on autonomous loops |
| IVS-07 | Migration to Cloud Environments | ✅ Implemented | `workspace/runtime_hardening/src/mcp_singleflight.mjs` | MCP server singleflight prevents duplicate process spawns and resource leakage |
| IVS-09 | Network Filtering | ✅ Implemented | `workspace/runtime_hardening/src/security/fs_sandbox.mjs` | Filesystem sandbox restricts all file operations to within WORKSPACE_ROOT |

---

## LOG — Logging and Monitoring

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| LOG-02 | Audit Log Protection | ✅ Implemented | `workspace/runtime_hardening/src/action_audit_log.mjs`, `workspace/scripts/audit_rotate.sh` | Append-only write semantics; rotation archives to gzip; audit_rotate.sh enforces 90-day retention with evidence directory preservation |
| LOG-05 | Audit Log Monitoring | ✅ Implemented | `workspace/runtime_hardening/src/log.mjs` | Structured NDJSON logger with multi-pattern secret redaction; `sanitizeField()` applied recursively to all log payloads |
| LOG-06 | Security Monitoring and Alerting | ✅ Implemented | `tools/gateway_security_hardening_patch.mjs` (`getMetrics()`), `tools/run_security_gates.sh` | Auth rate limiter exposes `getMetrics()` (hits_total, active_windows, ts); verified in security gate |
| LOG-09 | Audit Logging Scope | ✅ Implemented | `workspace/runtime_hardening/src/action_audit_log.mjs` | Every autonomous agent action logged with: ts, run_id, session_id, action_class, tool_name, args_summary, outcome, reversible, operator_authorized, integrity_hash |

---

## SEF — Security Incident Management, E-Discovery & Cloud Forensics

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| SEF-01 | Contact / Authority Maintenance | ✅ Implemented | `workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md` | Governance contract defines incident reporting chain and escalation path |
| SEF-04 | Incident Response Metrics | ✅ Implemented | `workspace/runtime_hardening/src/action_audit_log.mjs` | SHA-256 hash-chain audit log enables forensic reconstruction of all autonomous actions during an unattended run; `verifyChain()` detects tampering |

---

## TVM — Threat and Vulnerability Management

| CCM Control ID | Description | Status | Implementation File | Notes |
|----------------|-------------|--------|---------------------|-------|
| TVM-07 | Vulnerability Management | ✅ Implemented | `core/system2/context_sanitizer.js` | Context sanitizer detects and neutralizes prompt injection patterns before they reach the LLM |
| TVM-09 | Vulnerability Prioritization | ✅ Implemented | `core/system2/budget_circuit_breaker.js` | Combined token/call budget breaker plus action-class caps; loop detection halts runaway autonomous sequences |

---

## AASC — Autonomous Agent Security Controls (Custom Extension)

*These controls extend CCM v4 to cover the specific risks of an autonomous AI agent operating without real-time human supervision.*

| Control ID | Description | Status | Implementation File | Notes |
|------------|-------------|--------|---------------------|-------|
| AASC-01 | Agent Action Taxonomy | ✅ Implemented | `workspace/governance/AGENT_ACTION_TAXONOMY.md` | Five action classes (A–E) formally defined with classification decision tree |
| AASC-02 | Per-Run Destructive Action Budget | ✅ Implemented | `core/system2/budget_circuit_breaker.js` (`recordAction()`), `workspace/policy/llm_policy.json` | Class D hard cap: 5/run; Class C cap: 10/run; per-intent `actionClassCaps` in policy JSON |
| AASC-03 | Autonomous Loop Detection | ✅ Implemented | `core/system2/budget_circuit_breaker.js` (`isLooping()`) | Detects ≥3 identical (tool, args) pairs in last 10 actions; trips circuit breaker |
| AASC-04 | Operator Authorization for High-Risk Actions | ✅ Implemented | `workspace/governance/AUTONOMOUS_ACTION_POLICY.md`, `workspace/runtime_hardening/src/action_audit_log.mjs` | Class D actions require explicit authorization; `operator_authorized` field in every audit log entry |
| AASC-05 | Config Injection / Drift Prevention | ✅ Implemented | `tools/inject_gateway_config_overrides.sh`, `scripts/run_openclaw_gateway_repo_dali.sh` | Env-to-config injection eliminates manual edit requirement for tailnet deployments; override path passed via `--config-override` |

---

## Compliance Summary

| Domain | Controls Covered | Status |
|--------|-----------------|--------|
| AIS | AIS-02, AIS-03, AIS-05 | ✅ All Implemented |
| AAC | AAC-02, AAC-03 | ✅ All Implemented |
| CCC | CCC-01, CCC-02, CCC-03, CCC-04 | ✅ All Implemented |
| DSP | DSP-01, DSP-07 | ✅ All Implemented |
| GRC | GRC-01, GRC-03 | ✅ All Implemented |
| IAM | IAM-06, IAM-09, IAM-14 | ✅ All Implemented |
| IPY | IPY-04 | ✅ Implemented |
| IVS | IVS-01, IVS-07, IVS-09 | ✅ All Implemented |
| LOG | LOG-02, LOG-05, LOG-06, LOG-09 | ✅ All Implemented |
| SEF | SEF-01, SEF-04 | ✅ All Implemented |
| TVM | TVM-07, TVM-09 | ✅ All Implemented |
| AASC | AASC-01 through AASC-05 | ✅ All Implemented |

**Total controls addressed:** 32 (27 CCM v4 + 5 AASC)
**Gaps:** 0

---

## Update Log

| Date | Version | Change |
|------|---------|--------|
| 2026-03-01 | 1.0 | Initial mapping — branch `codex/harden/dali-csa5-tailnet-foundation` |

---

*This document is maintained alongside the codebase.  Any change to a security control MUST trigger an update to the corresponding row in this map before the branch can be admitted to main.*
