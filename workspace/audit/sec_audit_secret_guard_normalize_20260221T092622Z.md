# Audit Evidence: Normalize Audit Secret Guard Branch + CI Diff Scan Scope

- UTC start: Sat Feb 21 09:26:22 UTC 2026
- Branch under work: codex/sec/audit-secret-guard-20260221T090531Z
- Starting tip: ebfa6b6

## Phase 0 Baseline

### Command
```bash
date -u
git status --porcelain -uall
git rev-parse --short HEAD
```

### Output
```text
Sat Feb 21 09:26:09 UTC 2026
 M SOUL.md
 M memory/literature/state.json
 M scripts/daily_technique.py
 M scripts/get_daily_quote.js
 M workspace/knowledge_base/data/entities.jsonl
 M workspace/knowledge_base/data/last_sync.txt
 M workspace/research/data/papers.jsonl
 M workspace/teamchat/sessions/tacti_architecture_review.jsonl
?? workspace/audit/c_lawd_pr_merge_and_followups_20260221T080418Z.md
?? workspace/audit/fix_canonical_soul_drift_20260221T080815Z.md
?? workspace/audit/fix_groq_policy_alignment_20260221T081255Z.md
?? workspace/audit/fix_regression_bootstrap_config_20260221T081128Z.md
?? workspace/audit/pr_body_c_lawd_full_remediation_20260221.md
ebfa6b6
```

## Phase 1 Normalize Against origin/main

### Commands
```bash
git fetch origin
git merge-base --short origin/main HEAD || true
git merge-base origin/main HEAD
git diff --name-status origin/main...HEAD
```

### Key Output (pre-normalization)
```text
git merge-base --short ... => error: unknown option `short`
merge base: b463e9192f2a9300237ca346a920ef307bc4f3de

git diff --name-status origin/main...HEAD => contains extensive unrelated drift (many files outside the intended 9-path scope)
```

### Clean Rebase via Temporary Clean Worktree

### Commands
```bash
git worktree add -b tmp/sec-audit-secret-guard-clean /tmp/sec-audit-secret-guard-clean-20260221T0928 origin/main
cd /tmp/sec-audit-secret-guard-clean-20260221T0928
git cherry-pick 546d7eb
git cherry-pick 2997715
git cherry-pick 0f6b94e
git cherry-pick ebfa6b6
```

### Key Output
```text
Worktree created from origin/main at a2a0aa5
Cherry-pick conflict 1: .github/workflows/node_test.yml (resolved, preserved audit scan + governance guard)
Cherry-pick conflict 2: workspace/governance/GOVERNANCE_LOG.md (resolved, preserved AUDIT-2026-02-21-001 and -002)
```

### Post-normalization scope check (before new ci-diff edits)

### Command
```bash
git diff --name-status origin/main...HEAD
```

### Output
```text
M	.github/workflows/ci.yml
M	.github/workflows/node_test.yml
A	workspace/audit/sec_audit_secret_guard_20260221T090543Z.md
M	workspace/governance/GOVERNANCE_LOG.md
M	workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md
A	workspace/governance/audit_secret_allowlist.txt
M	workspace/scripts/hooks/pre-commit
A	workspace/scripts/install_git_hooks.sh
A	workspace/scripts/scan_audit_secrets.sh
```

## Phase 2 CI Diff-Scoped Scanning

### Changes made
- Added explicit mode parsing in `workspace/scripts/scan_audit_secrets.sh`:
  - `--mode staged` (existing behavior preserved)
  - `--mode ci-diff` (new)
- `ci-diff` behavior:
  - base ref: `origin/${GITHUB_BASE_REF}` else `origin/main`
  - best-effort fetch: `git fetch origin <base-branch> --depth=1 || true`
  - changed files: `git diff --name-only --diff-filter=ACMR "${base}"...HEAD | rg '^workspace/audit/'`
  - if zero changed files: PASS and exit 0
  - if base/diff unavailable: fallback to scan all tracked `workspace/audit/**`
- Updated workflows to call:
  - `bash workspace/scripts/scan_audit_secrets.sh --mode ci-diff`

## Phase 3 Verification

### Commands
```bash
bash -n workspace/scripts/scan_audit_secrets.sh
```

### Output
```text
(no output; syntax valid)
```

### Probe fail (staged mode)

### Commands
```bash
cat > workspace/audit/_tmp_secret_probe.md <<'PROBE'
# Temporary Probe

OPENCLAW_TOKEN=[REDACTED_TEST_PROBE]
PROBE
git add workspace/audit/_tmp_secret_probe.md
bash workspace/scripts/scan_audit_secrets.sh --mode staged
```

### Output
```text
FAIL audit-secret-scan: potential secret material detected in workspace/audit artifacts.
workspace/audit/_tmp_secret_probe.md:3:OPENCLAW_TOKEN=[REDACTED_TEST_PROBE]
Guidance: redact, replace with placeholders, re-run.
```

### Probe pass (staged mode, redacted)

### Commands
```bash
cat > workspace/audit/_tmp_secret_probe.md <<'PROBE'
# Temporary Probe

OPENCLAW_TOKEN=TOKEN_REDACTED_FOR_LOCAL_ENV
PROBE
git add workspace/audit/_tmp_secret_probe.md
bash workspace/scripts/scan_audit_secrets.sh --mode staged
```

### Output
```text
PASS audit-secret-scan: no non-allowlisted matches in 1 file(s) [mode=staged]
```

### Cleanup
```bash
git restore --staged workspace/audit/_tmp_secret_probe.md || true
rm -f workspace/audit/_tmp_secret_probe.md
```

### CI diff-mode local verification

### Command
```bash
CI=true bash workspace/scripts/scan_audit_secrets.sh --mode ci-diff
```

### Output
```text
PASS audit-secret-scan: no non-allowlisted matches in 1 file(s) [mode=ci-diff]
```

### Governance verification command

### Command
```bash
bash workspace/scripts/verify_governance_log.sh
```

### Output
```text
bash: workspace/scripts/verify_governance_log.sh: No such file or directory
```

### Note
`workspace/scripts/verify_governance_log.sh` is not present on `origin/main` or in the normalized commit set; command result recorded as evidence.
