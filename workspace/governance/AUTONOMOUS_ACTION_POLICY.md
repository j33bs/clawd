# Autonomous Action Policy
**Version:** 1.0
**Date:** 2026-03-01
**Framework:** CSA CCM v4 — IAM-09, GRC-01, AASC-01 through AASC-05
**Status:** Active

---

## Purpose

This policy defines the authorization matrix for each action class defined in `AGENT_ACTION_TAXONOMY.md`.  It specifies what the OpenClaw autonomous agent is permitted to do without real-time operator supervision, under what conditions, and what hard limits apply.

---

## Authorization Matrix

| Class | Name | Default Authorization | Env Override | Per-Run Cap | Hard Cap |
|-------|------|-----------------------|--------------|-------------|----------|
| A | Read-Only | Always permitted | — | Unlimited | — |
| B | Reversible Write | Permitted within budget | `OPENCLAW_CLASS_B_CAP` (int) | 20 writes/run | None |
| C | Service Control | Requires opt-in | `OPENCLAW_ALLOW_SERVICE_CONTROL=1` | 10 ops/run | 10 |
| D | Irreversible / High-Risk | Requires explicit authorization per action | `OPENCLAW_CLASS_D_CAP` (int, max 5) | 3 unauthorized/run | 5 with auth |
| E | Network Egress | Permitted if provider allowlisted | `OPENCLAW_PROVIDER_ALLOWLIST` | Per `llm_policy.json` | Per `llm_policy.json` |

---

## Class-by-Class Rules

### Class A — Always Permitted

No additional authorization required.  The agent may freely perform read-only operations at any time during an autonomous run.  High-frequency Class A operations (e.g., repeated LLM inference health checks) are subject to sampled audit logging.

### Class B — Per-Run Write Budget

The agent may perform up to **20 reversible writes per run** by default.  This cap can be adjusted via `OPENCLAW_CLASS_B_CAP` (integer, must be positive).  When the cap is reached, the agent MUST pause and surface an operator decision point before continuing.

The Budget Circuit Breaker (`BudgetCircuitBreaker`) tracks Class B counts and trips when the cap is reached.

### Class C — Service Control Opt-In

Service control actions (start/stop/restart daemons, reload configs, kill processes) are **disabled by default** during autonomous runs.  To enable:

```bash
export OPENCLAW_ALLOW_SERVICE_CONTROL=1
```

Even with this flag set, Class C actions are capped at **10 per run**.  Each action MUST be logged with service name, action type, and whether operator pre-authorization was recorded.

### Class D — Explicit Per-Action Authorization

Destructive or irreversible actions require an explicit operator authorization signal before execution.  Authorization forms:

1. **Prior approval entry** in the action audit log (recorded by a previous operator-supervised session with `operator_authorized: true`)
2. **Interactive confirmation** (when the agent is running in supervised mode)

Without authorization, the agent may execute at most **3 Class D actions per run** (emergency threshold for unavoidable side-effects like sending a Telegram error notification).

With authorization, the hard cap is **5 Class D actions per run** — this cannot be overridden by any env var.

Class D actions that exceed the cap cause the Budget Circuit Breaker to trip immediately, halting the run.

### Class E — Provider Allowlist and Token Budget

Outbound network calls to external providers are permitted if and only if:

1. The provider is listed in `OPENCLAW_PROVIDER_ALLOWLIST`
2. The call does not exceed the token or call budget in `workspace/policy/llm_policy.json`

The `actionClassCaps` field in `llm_policy.json` per-intent budget objects carries advisory caps for Class D and C actions within that intent's scope.

---

## Enforcement Points

| Mechanism | File | Controls |
|-----------|------|----------|
| Action-class caps (D, C) | `core/system2/budget_circuit_breaker.js` | AASC-02, AASC-04 |
| Loop detection | `core/system2/budget_circuit_breaker.js` | AASC-03 |
| Audit log (append-only) | `workspace/runtime_hardening/src/action_audit_log.mjs` | LOG-09, SEF-04 |
| Service control gate | `OPENCLAW_ALLOW_SERVICE_CONTROL` env check | IAM-09 |
| Provider allowlist | `OPENCLAW_PROVIDER_ALLOWLIST` + `llm_policy.json` | IPY-04 |

---

## Operator Authorization Workflow

When an autonomous run requires a Class D action and no prior authorization exists:

1. The agent MUST log the proposed action to the audit log with `operator_authorized: false`
2. The agent MUST surface a structured decision request (via Telegram reply if `TELEGRAM_REPLY_MODE=auto`, otherwise via structured stderr output)
3. The run MUST pause until the operator responds
4. On operator approval, the authorization is recorded (`operator_authorized: true`) and the action proceeds
5. On operator denial, the action is aborted and the audit log entry updated with `outcome: denied`

---

## Policy Violations

If any enforcement point is bypassed (e.g., hardcoded cap values modified, audit log truncated, circuit breaker disabled), the violation MUST be:

1. Logged to the security audit log at `fatal` level
2. Reported in the next governance review (see `SECURITY_GOVERNANCE_CONTRACT.md`)
3. Treated as a SEF-01 security incident

---

## Review Schedule

This policy is reviewed and updated:
- After any incident involving Class D or C actions
- When new tool categories are introduced that do not map cleanly to existing classes
- At each quarterly CSA CCM v4 compliance review

---

*Cross-reference: `AGENT_ACTION_TAXONOMY.md`, `CSA_CCM_V4_CONTROL_MAP.md`, `SECURITY_GOVERNANCE_CONTRACT.md`*
