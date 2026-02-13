# Triage Report: Quarantined Dirty Tree (2026-02-12)

## Executive summary
- Quarantined working tree analyzed on branch `redact/audit-evidence-20260212`.
- Change set is dominated by `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/**` evidence refreshes plus a small redaction tooling/test pair.
- Portable recovery bundle was created under `workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/` with tracked patches, untracked archive, manifests, and restore instructions.
- No `git stash`, `git reset`, `git clean`, branch switch, or commit was performed.

## Dirty tree identity + metadata
- Repo root: `/Users/heathyeager/clawd`
- Branch: `redact/audit-evidence-20260212`
- HEAD: `c2583819dc877e1b19abdfbb2b4ad6c8cdf4486c`
- Remote: `origin git@github.com:j33bs/clawd.git`

### Command snapshots (bounded)
`git status --porcelain=v1 -uall` (first lines):
```text
 M workspace/docs/audits/SYSTEM2-AUDIT-2026-02-11.md
 M workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/backups/20260211T232324/openclaw.json.bak.redacted
 M workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase0_env_versions.txt
 M workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase0_repo_state.txt
 M workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/phase1_error_bursts_excerpt.txt
 ... (full list in `workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/status_porcelain.txt`)
```

`git log --oneline --decorate -20` (first lines):
```text
c258381 (HEAD -> redact/audit-evidence-20260212, codex/audit/system2-postfix-20260211) fix(system2): fail-closed RCE posture + auth circuit breakers + snapshot wiring
6f860f9 (codex/audit/system2-20260211) docs(audit): add system2 audit evidence bundle and remediation report
4823f85 (tag: governance/audit-hardening-v1-2026-02-09-main, tag: governance/audit-hardening-v1-2026-02-09, feature/system2-design-brief) Audit Layer v1: opt-in integration hooks
```

## Bundle contents (exported artifacts)
Bundle path: `workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/`

- `tracked_worktree.patch`
- `staged_index.patch`
- `status_porcelain.txt`
- `name_status.txt`
- `diff_stat.txt`
- `untracked_files.txt`
- `untracked_files.tgz`
- `RESTORE.md`
- `bundle_manifest.json`
- `numstat_sorted.tsv`
- `all_changed_paths_raw.txt`
- `all_changed_paths_source_only.txt`
- `category_counts_raw.tsv`
- `category_counts_source_only.tsv`

Line/size highlights:
- `status_porcelain.txt`: 89 lines
- `name_status.txt`: 79 lines
- `untracked_files.txt`: 13 lines
- `tracked_worktree.patch`: 1,164,784 bytes
- `untracked_files.tgz`: 97,893 bytes

## Category breakdown
Source-only counts exclude self-generated files under `workspace/docs/audits/QUARANTINE-BUNDLE-2026-02-12/`.

| Category | File count | Top paths by churn (from `numstat_sorted.tsv`) | Risk | Notes |
|---|---:|---|---|---|
| `.github/` | 0 | n/a | Low | No CI/workflow delta in quarantined tree.
| `scripts/` | 1 | untracked only (`scripts/redact_audit_evidence.js`) | Medium | Tooling logic; needs tests and deterministic behavior check.
| `core/` | 0 | n/a | High | No runtime/core delta currently dirty.
| `tests/` | 1 | untracked only (`tests/redact_audit_evidence.test.js`) | Low | Deterministic unit test candidate.
| `workspace/docs/` | 84 | `phase1_tmp_openclaw_tail500.txt` (1000), `phase4_memory_search_signatures.txt` (144), `phase4_source_files.txt` (142), `phase3_keyword_scan.txt` (142), `phase2_workspace_identity.txt` (118) | Low-Medium | Mostly audit/evidence refreshes; large generated/log payloads.
| `schemas/` | 0 | n/a | Low | No schema delta.
| `notes/` | 0 | n/a | Low | No notes delta.
| `config files` | 0 | n/a | High | No package/openclaw config files changed in dirty set.
| `other` | 0 | n/a | Low | None.

## Proposed PR bundles (A–F)
### A) docs-only
- Bundle name: `triage/docs-001-audit-narrative`
- Included paths:
  - `workspace/docs/audits/SYSTEM2-AUDIT-2026-02-11.md`
  - `workspace/docs/audits/MERGE-EXEC2-2026-02-12.md`
  - `workspace/docs/audits/NEXTSTEPS-EXEC2-2026-02-12.md`
  - `workspace/docs/audits/POSTMERGE-VALIDATION-2026-02-12.md`
  - `workspace/docs/audits/REDACTION-REPORT-2026-02-12.md`
- Why grouped: human-readable governance/audit narrative files only.
- Risk: Low
- Recommended gates: markdown render sanity + link/path sanity (optional), no runtime gate required.
- Suggested salvage branch: `triage/docs-001`

### B) CI/workflows-only
- Bundle name: `triage/ci-001` (none currently present)
- Included paths: none in quarantined dirty set.
- Why grouped: reserved category for future splits.
- Risk: n/a
- Recommended gates: n/a
- Suggested salvage branch: `triage/ci-001` (only if future CI deltas are extracted)

### C) tooling/scripts-only
- Bundle name: `triage/tooling-001-redaction`
- Included paths:
  - `scripts/redact_audit_evidence.js`
  - `tests/redact_audit_evidence.test.js`
  - optionally `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/postfix_rce/redaction_manifest.txt` as fixture/evidence
- Why grouped: isolated redaction tool + direct test pair.
- Risk: Medium
- Recommended gates: `npm test`, `npm run gate:module-resolution`.
- Suggested salvage branch: `triage/tooling-001`

### D) runtime/core changes
- Bundle name: `triage/runtime-001`
- Included paths: none present under `core/` in dirty state.
- Why grouped: explicit placeholder; do not infer runtime deltas from docs evidence churn.
- Risk: High if created without new evidence.
- Recommended gates: `npm ci && npm test` plus module-resolution gate.
- Suggested salvage branch: `triage/runtime-001` (defer)

### E) tests-only
- Bundle name: `triage/tests-001-redaction`
- Included paths:
  - `tests/redact_audit_evidence.test.js`
- Why grouped: optional if test should land independently before script changes.
- Risk: Low
- Recommended gates: `npm test`.
- Suggested salvage branch: `triage/tests-001`

### F) mixed (needs split)
- Bundle name: `triage/mixed-001-evidence-refresh`
- Included paths:
  - `workspace/docs/audits/SYSTEM2-EVIDENCE-2026-02-11/**`
- Why grouped: large generated evidence/log refresh touching many snapshots and phase outputs; should be split by phase/topic before PR.
- Risk: Medium
- Recommended gates: audit diff review, secret scan, artifact size sanity.
- Suggested salvage branch: `triage/mixed-001`

## Recommended salvage order
1. `triage/docs-001` (docs-only narrative updates, lowest risk)
2. `triage/tests-001` (if test can stand alone)
3. `triage/tooling-001` (script + test together, gated)
4. `triage/mixed-001` (split evidence refresh into smaller docs PRs)
5. `triage/runtime-001` (only if runtime deltas are later identified)

For each bundle, prefer path-limited patch porting from quarantine to clean branch. Stop if gates fail or if content cannot be split cleanly.

## Stop conditions / risks
- Stop if module-resolution gate or `npm test` fails on tooling bundle.
- Stop if evidence bundles contain secret-like material (re-run targeted secret scan before PR).
- Stop if mixed bundle cannot be partitioned without semantic ambiguity.

## Secret-like pattern check
- High-confidence scan over exported patch/manifests found no matches for common token/key signatures (`gh*`, `AKIA/ASIA`, `xox*`, PEM private key headers).

## Confirmation
- No destructive or state-changing git operations were used on the quarantined tree.
- Only read-only git commands plus local artifact writes (bundle/report generation) were executed.
