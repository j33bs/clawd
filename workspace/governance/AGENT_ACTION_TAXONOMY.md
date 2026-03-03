# Agent Action Taxonomy
**Version:** 1.0
**Date:** 2026-03-01
**Framework:** CSA CCM v4 — IAM-09, GRC-01
**Status:** Active

---

## Purpose

This document formally classifies every category of action an OpenClaw autonomous agent may perform.  The taxonomy is the normative reference for the Autonomous Action Policy (`AUTONOMOUS_ACTION_POLICY.md`), the Action Audit Log (`action_audit_log.mjs`), and the Budget Circuit Breaker action-class caps.

An "action" is any operation the agent executes via a tool call, shell invocation, API call, or direct file/service mutation.

---

## Action Classes

### Class A — Read-Only

**Definition:** Operations that observe system state without modifying any persistent resource.

**Examples:**
- LLM inference calls (prompt → response, no side-effects)
- Reading files, directory listings, git log/status/diff
- Querying local service health endpoints
- Memory reads (reading existing session/workspace state)
- Non-mutating tool calls (status checks, diagnostics)
- Fetching external URLs for read purposes (no POST/PUT/DELETE)

**Audit requirement:** Sampled logging (1-in-10 for high-frequency ops, all for rare ops).
**Authorization:** Always permitted during an autonomous run.

---

### Class B — Reversible Write

**Definition:** Operations that create or modify resources that can be fully reversed via standard tooling (e.g., git revert, file restore from git history).

**Examples:**
- Editing or creating files that are tracked in a git repository
- Writing or updating workspace memory files (`.agent_workspace/`)
- Updating local config files (non-credential, within WORKSPACE_ROOT)
- Creating new git branches or commits (local, not pushed)
- Writing temporary files within the agent workspace

**Audit requirement:** Every instance logged.
**Authorization:** Permitted up to per-run write budget (default: 20 writes/run).

---

### Class C — Service Control

**Definition:** Operations that start, stop, restart, or reconfigure running system services, daemons, or processes.

**Examples:**
- Starting or stopping systemd units
- Reloading service configs (e.g., `nginx -s reload`, `systemctl reload`)
- Spawning or killing background processes
- Toggling feature flags that affect running services
- Reconfiguring network interfaces or firewall rules

**Audit requirement:** Every instance logged with service name, action, and operator-authorization status.
**Authorization:** Requires `OPENCLAW_ALLOW_SERVICE_CONTROL=1` env var or prior operator authorization recorded in the action audit log.  Per-run cap: 10.

---

### Class D — Irreversible / High-Risk

**Definition:** Operations whose effects cannot be trivially undone, or that carry significant blast radius if executed incorrectly.

**Examples:**
- Deleting files, directories, or database records
- `git push` to any remote (including force-push)
- Credential rotation or API key regeneration
- Package installations (`apt install`, `npm install -g`, `pip install`)
- Outbound messages to external communication platforms (Telegram, Slack, email)
- Destructive shell commands (`rm -rf`, `truncate`, `dd`)
- Schema migrations that drop columns or tables
- Overwriting non-git-tracked files

**Audit requirement:** Every instance logged with full args summary and explicit operator-authorization reference.
**Authorization:** Requires explicit operator authorization per action (recorded in audit log).
Default per-run cap: 3 unauthorized.
Hard cap: 5 even with authorization.

---

### Class E — Network Egress

**Definition:** Outbound network calls to external systems beyond the local tailnet.

**Examples:**
- API calls to paid LLM providers (Anthropic, OpenAI, Groq, xAI, Qwen)
- Webhook deliveries to external endpoints
- Calls to third-party APIs (GitHub, package registries, search)
- Any HTTP/HTTPS request to a non-loopback, non-tailnet destination

**Audit requirement:** Every instance logged with provider, endpoint domain, and estimated token/cost impact.
**Authorization:** Permitted if the provider is in the `OPENCLAW_PROVIDER_ALLOWLIST`; subject to token/call budgets defined in `workspace/policy/llm_policy.json`.

---

## Classification Decision Tree

```
Is the action purely observational (no persistent mutation)?
  YES → Class A

Does the action modify a git-tracked resource reversibly?
  YES → Class B

Does the action control a running service or process?
  YES → Class C

Does the action delete, push to remote, install packages,
send external messages, or otherwise produce hard-to-reverse effects?
  YES → Class D

Does the action make outbound network calls to non-local endpoints?
  YES → Class E
```

When an action spans multiple classes (e.g., a tool that edits a file AND sends a webhook), assign the **highest** applicable class.

---

## Relationship to Other Controls

| Control | Reference |
|---------|-----------|
| Per-class caps enforcement | `core/system2/budget_circuit_breaker.js` |
| Per-run audit log | `workspace/runtime_hardening/src/action_audit_log.mjs` |
| Authorization policy | `workspace/governance/AUTONOMOUS_ACTION_POLICY.md` |
| CCM v4 mapping | `workspace/governance/CSA_CCM_V4_CONTROL_MAP.md` |

---

*This document is a living governance artifact.  Update it whenever new tool categories are introduced or existing tool behaviors change.*
