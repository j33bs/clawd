# Audit Evidence Redaction Report

**Date:** 2026-02-11T19:48:23.130Z
**Mode:** apply
**Script version:** 1.0.0
**Script SHA-256:** `9ebdb6bfe04943e56a91e3925f61fb01c3b6169485d6da2dd0b858b63ff89989`
**Root scanned:** `{{REPO_ROOT}}/workspace/docs/audits`

## Summary

| Metric | Count |
|--------|-------|
| Files scanned | 122 |
| Files changed | 79 |
| Files skipped (binary/read error) | 0 |
| Files skipped (too large) | 0 |
| Files skipped (JSON invalid after redaction) | 0 |

## Patterns Redacted

| Pattern ID | Replacement | Count |
|------------|-------------|-------|
| `repo_root_path` | `{{REPO_ROOT}}` | 242 |
| `home_openclaw_path` | `{{HOME}}/.openclaw` | 148 |
| `home_path` | `{{HOME}}` | 768 |
| `ls_owner_group` | `\$1{{USER}}\$2{{GROUP}}\$4` | 88 |
| `username` | `{{USER}}` | 960 |

## Changed Files

- `workspace/docs/audits/SYSTEM2-AUDIT-2026-02-11.md`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/backups/20260211T232324/openclaw.json.bak.redacted`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase0_env_versions.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase0_repo_state.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_error_bursts_excerpt.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_failure_signatures.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_gateway_err_log_tail500.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_gateway_log_tail500.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_launchctl_filtered.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_log_inventory.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_runtime_topology.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_signature_counts_refined.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_tmp_openclaw_inventory.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_tmp_openclaw_tail500.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_config_discovery.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_openclaw_config_redacted.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_openclaw_health.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_openclaw_health_parsed.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_openclaw_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_openclaw_status.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_openclaw_status_parsed.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_status_health_highlights.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_workspace_identity.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_approvals_allowlist_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_approvals_get.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_approvals_get_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_approvals_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_keyword_scan.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_node_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_node_run_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_nodes_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_nodes_invoke_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_nodes_list.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_nodes_run_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_pairing_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_runtime_state_files.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_security_audit.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_security_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_system_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase4_core_system2_tree.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase4_federation_search.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase4_memory_search_signatures.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase4_runtime_observability_logs.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase4_source_files.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase4_system2_observability_artifacts.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_backup_listing.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_backup_locations.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_before_after_comparison.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_doctor_help.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_openclaw_config_checksums.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_openclaw_config_diff.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_postfix_approvals_get.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_postfix_health.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_postfix_highlights.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_postfix_log_excerpt.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase5_postfix_status.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_auth/postfix_auth_provider_profile_extract.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_core_system2/postfix_core_system2_inventory.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/postfix_health.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/postfix_health_raw.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/postfix_snapshot_listing.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/postfix_snapshot_stdout.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/postfix_status.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/postfix_status_raw.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/snapshots/20260211T134517Z/approvals_get.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/snapshots/20260211T134517Z/approvals_get_raw.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/snapshots/20260211T134517Z/health.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/snapshots/20260211T134517Z/health_raw.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/snapshots/20260211T134517Z/manifest.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/snapshots/20260211T134517Z/status.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/snapshots/20260211T134517Z/status_raw.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_obs/snapshots/20260211T134517Z/system2_snapshot_event.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_rce/postfix_approvals_get.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_rce/postfix_approvals_get_raw.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_rce/postfix_phase0_repo_state.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_rce/postfix_rce_keyword_scan_targeted.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_rce/postfix_rce_policy_fields.txt`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_rce/postfix_rce_posture_result.json`
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_rce/postfix_rce_posture_stdout.txt`

## Skipped Files

- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_openclaw_health.json`: json_already_invalid_redacted_as_text
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase2_openclaw_status.json`: json_already_invalid_redacted_as_text
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_approvals_get.json`: json_already_invalid_redacted_as_text
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_nodes_list.json`: json_already_invalid_redacted_as_text
- `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase3_security_audit.json`: json_already_invalid_redacted_as_text

## Sample Lines (before/after)

### `workspace/docs/audits/SYSTEM2-AUDIT-2026-02-11.md` line 23

**Before:**
```
| Unsupported config key caused schema-invalid runtime config (fixed) | `phase0_env_versions.txt`, `phase2_openclaw_help.txt`, `phase2_openclaw_health.json`, `phase2_openclaw_status.json`, `phase5_pos
```
**After:**
```
| Unsupported config key caused schema-invalid runtime config (fixed) | `phase0_env_versions.txt`, `phase2_openclaw_help.txt`, `phase2_openclaw_health.json`, `phase2_openclaw_status.json`, `phase5_pos
```

### `workspace/docs/audits/SYSTEM2-AUDIT-2026-02-11.md` line 37

**Before:**
```
- File changed: `{{HOME}}/.openclaw/openclaw.json`
```
**After:**
```
- File changed: `{{HOME}}/.openclaw/openclaw.json`
```

### `workspace/docs/audits/SYSTEM2-AUDIT-2026-02-11.md` line 42

**Before:**
```
- Private raw backup (non-bundle): `{{HOME}}/.openclaw/audit-backups/20260211T232324/openclaw.json.bak`
```
**After:**
```
- Private raw backup (non-bundle): `{{HOME}}/.openclaw/audit-backups/20260211T232324/openclaw.json.bak`
```

### `workspace/docs/audits/SYSTEM2-AUDIT-2026-02-11.md` line 52

**Before:**
```
- Workspace/memory attribution now points to `{{REPO_ROOT}}` in status output (`phase5_before_after_comparison.txt`).
```
**After:**
```
- Workspace/memory attribution now points to `{{REPO_ROOT}}` in status output (`phase5_before_after_comparison.txt`).
```

### `workspace/docs/audits/SYSTEM2-AUDIT-2026-02-11.md` line 60

**Before:**
```
1. Restore backup: copy `{{HOME}}/.openclaw/audit-backups/20260211T232324/openclaw.json.bak` to `{{HOME}}/.openclaw/openclaw.json`.
```
**After:**
```
1. Restore backup: copy `{{HOME}}/.openclaw/audit-backups/20260211T232324/openclaw.json.bak` to `{{HOME}}/.openclaw/openclaw.json`.
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/backups/20260211T232324/openclaw.json.bak.redacted` line 43

**Before:**
```
      "google-gemini-cli:{{USER}}@gmail.com": {
```
**After:**
```
      "google-gemini-cli:{{USER}}@gmail.com": {
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/backups/20260211T232324/openclaw.json.bak.redacted` line 46

**Before:**
```
        "email": "{{USER}}@gmail.com"
```
**After:**
```
        "email": "{{USER}}@gmail.com"
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/backups/20260211T232324/openclaw.json.bak.redacted` line 218

**Before:**
```
      "workspace": "{{HOME}}/.openclaw/workspace",
```
**After:**
```
      "workspace": "{{HOME}}/.openclaw/workspace",
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/backups/20260211T232324/openclaw.json.bak.redacted` line 240

**Before:**
```
        "workspace": "{{REPO_ROOT}}",
```
**After:**
```
        "workspace": "{{REPO_ROOT}}",
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/backups/20260211T232324/openclaw.json.bak.redacted` line 241

**Before:**
```
        "agentDir": "{{HOME}}/.clawdbot/agents/main/agent"
```
**After:**
```
        "agentDir": "{{HOME}}/.clawdbot/agents/main/agent"
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/backups/20260211T232324/openclaw.json.bak.redacted` line 320

**Before:**
```
        "{{REPO_ROOT}}/skills"
```
**After:**
```
        "{{REPO_ROOT}}/skills"
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase0_env_versions.txt` line 17

**Before:**
```
Invalid config at {{HOME}}/.openclaw/openclaw.json:\n- models.providers.system2-litellm: Unrecognized key: "note"
```
**After:**
```
Invalid config at {{HOME}}/.openclaw/openclaw.json:\n- models.providers.system2-litellm: Unrecognized key: "note"
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase0_repo_state.txt` line 3

**Before:**
```
cwd={{REPO_ROOT}}
```
**After:**
```
cwd={{REPO_ROOT}}
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase0_repo_state.txt` line 6

**Before:**
```
{{REPO_ROOT}}
```
**After:**
```
{{REPO_ROOT}}
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_error_bursts_excerpt.txt` line 207

**Before:**
```
14:2026-01-29T14:02:38.951Z [ws] ⇄ res ✗ agent errorCode=UNAVAILABLE errorMessage=FailoverError: No API key found for provider "anthropic". Auth store: {{HOME}}/.clawdbot/agents/main/agent/a
```
**After:**
```
14:2026-01-29T14:02:38.951Z [ws] ⇄ res ✗ agent errorCode=UNAVAILABLE errorMessage=FailoverError: No API key found for provider "anthropic". Auth store: {{HOME}}/.clawdbot/agents/main/agent/auth-profil
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_failure_signatures.txt` line 4

**Before:**
```
## File: {{HOME}}/.openclaw/logs/gateway.log
```
**After:**
```
## File: {{HOME}}/.openclaw/logs/gateway.log
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_failure_signatures.txt` line 13

**Before:**
```
734:2026-01-30T18:00:21.401Z [canvas] host mounted at http://127.0.0.1:18789/__clawdbot__/canvas/ (root {{REPO_ROOT}}/canvas)
```
**After:**
```
734:2026-01-30T18:00:21.401Z [canvas] host mounted at http://127.0.0.1:18789/__clawdbot__/canvas/ (root {{REPO_ROOT}}/canvas)
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_failure_signatures.txt` line 24

**Before:**
```
14:2026-01-29T14:02:38.951Z [ws] ⇄ res ✗ agent errorCode=UNAVAILABLE errorMessage=FailoverError: No API key found for provider "anthropic". Auth store: {{HOME}}/.clawdbot/agents/main/agent/a
```
**After:**
```
14:2026-01-29T14:02:38.951Z [ws] ⇄ res ✗ agent errorCode=UNAVAILABLE errorMessage=FailoverError: No API key found for provider "anthropic". Auth store: {{HOME}}/.clawdbot/agents/main/agent/auth-profil
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_failure_signatures.txt` line 40

**Before:**
```
## File: {{HOME}}/.openclaw/logs/gateway.err.log
```
**After:**
```
## File: {{HOME}}/.openclaw/logs/gateway.err.log
```

### `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_failure_signatures.txt` line 67

**Before:**
```
296221:2026-02-10T15:20:54.152Z Embedded agent failed before reply: All models failed (12): google-gemini-cli/gemini-3-pro-preview: LLM request timed out. (unknown) | anthropic/claude-opus-4-6: HTTP 4
```
**After:**
```
296221:2026-02-10T15:20:54.152Z Embedded agent failed before reply: All models failed (12): google-gemini-cli/gemini-3-pro-preview: LLM request timed out. (unknown) | anthropic/claude-opus-4-6: HTTP 4
```

## Verification Steps

```bash
# Confirm zero remaining occurrences:
# Search for any remaining absolute home-directory paths or usernames:
grep -rIE '/(Us)ers/[a-zA-Z]' workspace/docs/audits/ | wc -l  # expect 0
grep -rI '{{USER}}' workspace/docs/audits/ | wc -l             # expect 0  (username was redacted)

# Confirm JSON validity:
find workspace/docs/audits -name '*.json' -exec node -e 'JSON.parse(require("fs").readFileSync(process.argv[1],"utf8"))' {} \;

# Revert if needed:
git revert <commit-sha>
```
