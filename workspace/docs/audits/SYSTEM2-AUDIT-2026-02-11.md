# SYSTEM2 Audit (2026-02-11)

## Executive Summary

### What is healthy
- Gateway process is running on loopback only (`127.0.0.1:18789`) and discoverable via launchd.
- After remediation, config is schema-valid and read-only security introspection commands work again.
- Node host service is not installed; paired/pending node lists are currently empty.
- Telegram policy is configured as `dmPolicy=pairing` and `groupPolicy=allowlist` in effective config.

### What is broken
- Prior to remediation, the effective config had an unsupported key (`models.providers.system2-litellm.note`) that forced best-effort mode and broke multiple audit/control commands.
- Runtime logs show persistent auth/provider/network failure churn (invalid bearer token, missing API keys, quota errors, repeated fetch failures).

### What is risky
- RCE-capable surfaces exist (`nodes run`, `node run`, `system.run` path), and `tools.elevated` remains enabled; approvals/allowlist policy is currently minimal (empty defaults file).
- System-2 observability/federation contracts exist in repo code, but active runtime artifacts for System-2 events are absent, creating monitoring blind spots.

## Findings Table

| Finding | Evidence refs | Impact | Likelihood | Recommendation | Minimal fix | Reversibility |
|---|---|---|---|---|---|---|
| Unsupported config key caused schema-invalid runtime config (fixed) | `phase0_env_versions.txt`, `phase2_openclaw_help.txt`, `phase2_openclaw_health.json`, `phase2_openclaw_status.json`, `phase5_postfix_version.txt`, `phase5_before_after_comparison.txt` | Control-plane introspection failed; security status and workspace/memory attribution became inconsistent | High | Keep runtime config strictly schema-valid; add preflight validation before service reloads | Removed `models.providers.system2-litellm.note` from `{{HOME}}/.openclaw/openclaw.json` | Raw backup retained at `{{HOME}}/.openclaw/audit-backups/20260211T232324/openclaw.json.bak`; redacted backup in evidence; unified diff captured |
| RCE surface exists via node pairing + remote command execution | `phase3_node_help.txt`, `phase3_nodes_help.txt`, `phase3_nodes_run_help.txt`, `phase3_approvals_help.txt`, `phase3_approvals_allowlist_help.txt`, `phase5_postfix_status.json`, `phase5_postfix_approvals_get.json`, `phase5_postfix_nodes_list.json` | If mis-scoped approvals/allowlists are introduced, remote shell execution can occur on paired nodes | Medium currently (paired=0), High if pairing is enabled and policy broadens | Enforce deny-by-default exec policy (`allowlist` mode + explicit approvals entries) and keep node service disabled unless intentionally required | No runtime permission broadening performed | N/A (read-only audit evidence only) |
| Auth/provider loop signatures indicate quota burn + degraded reliability | `phase1_signature_counts_refined.txt`, `phase1_error_bursts_excerpt.txt`, `phase4_error_burst_metrics.txt`, `phase5_postfix_log_excerpt.txt` | Elevated failure traffic, wasted quota, delayed/failed responses | High | Repair/rotate invalid credentials; prune unavailable providers from fallback list; keep cooldown/circuit-breaker behavior explicit | No credential mutations performed (secret-safe audit) | N/A |
| Telegram channel exhibits retry/fetch-failure churn (loop risk) | `phase1_gateway_err_log_tail500.txt`, `phase1_error_bursts_excerpt.txt`, `phase4_error_burst_metrics.txt`, `phase5_postfix_log_excerpt.txt` | Channel response instability; potential repeated retry load | High | Add/verify fail-fast classification and cooldown pause window for repeated network failures; consider temporary channel pause during outage windows | No channel disablement applied (to avoid service interruption without explicit approval) | N/A |
| System-2 observability/federation contracts are defined but not operationally wired | `phase4_core_system2_tree.txt`, `phase4_policy_code_excerpts.txt`, `phase4_federation_search.txt`, `phase4_system2_observability_artifacts.txt` | Monitoring and handshake assumptions can drift from reality; weak production-grade assurance for System-2 | Medium | Wire emitter into active runtime path; emit startup probes; add integration checks for federation/handshake invariants | No code refactor applied (minimal-diff constraint) | N/A |

## High-Risk Focus Checks (Explicit)
- Node pairing / remote exec (`system.run`/`nodes run`): **checked**; capability exists and is approval-model dependent.
- Channel-triggered loop risk (Telegram): **checked**; repeated network retry and fetch-failure signatures observed.
- Auth loop signatures: **checked**; repeated auth and quota failure signatures observed with bounded excerpts and counts.

## What Changed

### Remediation Applied
- File changed: `{{HOME}}/.openclaw/openclaw.json`
- Change: removed unsupported key `models.providers.system2-litellm.note` only.

### Backup + Diff Artifacts
- Backup location metadata: `phase5_backup_locations.txt`
- Private raw backup (non-bundle): `{{HOME}}/.openclaw/audit-backups/20260211T232324/openclaw.json.bak`
- Redacted backup in evidence: `backups/20260211T232324/openclaw.json.bak.redacted`
- Unified diff: `phase5_openclaw_config_diff.txt`
- Checksums: `phase5_openclaw_config_checksums.txt`

### Post-Fix Validation Outcomes
- Config invalid banner removed (`phase5_postfix_version.txt`).
- `openclaw approvals get --json` now succeeds (`phase5_postfix_approvals_get.json`).
- `openclaw nodes list --json` now succeeds (`phase5_postfix_nodes_list.json`).
- Security summary improved from `critical:1` to `critical:0`; `gateway.loopback_no_auth` finding cleared (`phase5_before_after_comparison.txt`).
- Workspace/memory attribution now points to `{{REPO_ROOT}}` in status output (`phase5_before_after_comparison.txt`).

## Command Log + Outcomes
See raw command outputs and snapshots under:
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/`
- Evidence manifest: `phase5_evidence_manifest.txt`

## Revert Procedure
1. Restore backup: copy `{{HOME}}/.openclaw/audit-backups/20260211T232324/openclaw.json.bak` to `{{HOME}}/.openclaw/openclaw.json`.
2. Validate: run `openclaw --version` and `openclaw status --json`.
3. Confirm rollback delta with `phase5_openclaw_config_diff.txt`.

## Secret Hygiene Check
- Evidence bundle scanned post-sanitization with heuristic patterns.
- Result: no secret-like matches in evidence folder (`phase5_evidence_secret_scan.txt`).
