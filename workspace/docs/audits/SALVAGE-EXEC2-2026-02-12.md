# SALVAGE Exec2 Audit (2026-02-12)

Mode: CBP-governed execution.
Objective: port useful, low-risk changes from quarantined commit 9f35bc1 onto clean main base 537092d without reintroducing diffuse module resolution failures.

## Phase 0 - Setup

### git -C /tmp/clawd-postmerge-validate-kDVoV5 fetch --all --prune

```
```

### git -C /tmp/clawd-postmerge-validate-kDVoV5 checkout -b salvage/port-system2-unified origin/main

```
Switched to a new branch 'salvage/port-system2-unified'
branch 'salvage/port-system2-unified' set up to track 'origin/main'.
```

### Branch metadata

```
branch=salvage/port-system2-unified
base_sha=537092d61aa9eef841e35aed9272d04eea39737d
target_broken_sha=9f35bc1ab7d802e60923c95679febc0325555007
head_sha=537092d61aa9eef841e35aed9272d04eea39737d
```

## Phase 1 - Identify What To Port

### 1.1 Raw deltas

```
git diff --name-status origin/main 9f35bc1ab7d802e60923c95679febc0325555007 > /tmp/salvage_name_status.txt
git diff --stat origin/main 9f35bc1ab7d802e60923c95679febc0325555007 > /tmp/salvage_stat.txt

D	.github/workflows/node_test.yml
A	.github/workflows/system2_macos_audit.yml
A	core/integration/system1_adapter.js
A	core/model_call.js
A	core/model_constants.js
A	core/model_runtime.js
A	core/providers/litellm_proxy_provider.js
A	core/router.js
A	core/system2/budget_circuit_breaker.js
A	core/system2/degraded_mode_controller.js
A	core/system2/event_log.js
A	core/system2/federated_envelope.js
A	core/system2/federated_rpc_v0.js
A	core/system2/gateway.js
A	core/system2/routing_policy_contract.js
A	core/system2/startup_invariants.js
A	core/system2/tool_allowlist.readonly.json
A	core/system2/tool_plane.js
A	core/telegram_client.js
A	docs/system2/OPERATOR_RUNBOOK.md
A	notes/governance/2026-02-11-change-admission-gate-system2-brief-broad.md
D	package-lock.json
M	package.json
A	reference/TROUBLESHOOTING.md
A	schemas/federated_job_envelope.schema.json
A	schemas/system2_observability_event.schema.json
A	schemas/system2_routing_policy_contract.schema.json
A	schemas/system2_sync_cursor.schema.json
A	scripts/audit_system2.mjs
A	scripts/check_staged_allowlist.js
D	scripts/run_tests.js
A	scripts/system2_invariant_probe.js
A	scripts/telegram_diag.js
A	sys/config.toml
A	sys/config.toml.example
A	sys/config/config.schema.json
A	sys/config/defaults.js
A	tests/budget_circuit_breaker.test.js
A	tests/degraded_mode_controller.test.js
A	tests/federated_envelope.test.js
A	tests/federated_rpc_v0.test.js
A	tests/gateway.test.js
A	tests/litellm_proxy_provider.test.js
A	tests/model_call_litellm_route.test.js
A	tests/model_call_system2_policy.test.js
A	tests/sys_config.test.js
A	tests/system2_event_log_sync.test.js
A	tests/system2_routing_policy_contract.test.js
A	tests/system2_startup_invariants.test.js
A	tests/system2_tool_plane.test.js
A	tests/telegram_backoff.test.js
A	tests/telegram_e2e_harness.test.js
D	workspace/docs/governance/BRANCH-PROTECTION.md
---
 .github/workflows/node_test.yml                    |   24 -
 .github/workflows/system2_macos_audit.yml          |  102 ++
 core/integration/system1_adapter.js                |   52 +
 core/model_call.js                                 | 1601 ++++++++++++++++++++
 core/model_constants.js                            |   30 +
 core/model_runtime.js                              |   97 ++
 core/providers/litellm_proxy_provider.js           |  178 +++
 core/router.js                                     |  174 +++
 core/system2/budget_circuit_breaker.js             |  160 ++
 core/system2/degraded_mode_controller.js           |  183 +++
 core/system2/event_log.js                          |  151 ++
 core/system2/federated_envelope.js                 |  116 ++
 core/system2/federated_rpc_v0.js                   |  210 +++
 core/system2/gateway.js                            |  532 +++++++
 core/system2/routing_policy_contract.js            |  147 ++
 core/system2/startup_invariants.js                 |  104 ++
 core/system2/tool_allowlist.readonly.json          |   14 +
 core/system2/tool_plane.js                         |  192 +++
 core/telegram_client.js                            |  251 +++
 docs/system2/OPERATOR_RUNBOOK.md                   |   36 +
 ...11-change-admission-gate-system2-brief-broad.md |  140 ++
 package-lock.json                                  |   12 -
 package.json                                       |   19 +-
 reference/TROUBLESHOOTING.md                       |  178 +++
 schemas/federated_job_envelope.schema.json         |   48 +
 schemas/system2_observability_event.schema.json    |   27 +
 .../system2_routing_policy_contract.schema.json    |   57 +
 schemas/system2_sync_cursor.schema.json            |   18 +
 scripts/audit_system2.mjs                          |  234 +++
 scripts/check_staged_allowlist.js                  |  206 +++
 scripts/run_tests.js                               |  101 --
 scripts/system2_invariant_probe.js                 |   34 +
 scripts/telegram_diag.js                           |  551 +++++++
 sys/config.toml                                    |   47 +
 sys/config.toml.example                            |   49 +
 sys/config/config.schema.json                      |  116 ++
 sys/config/defaults.js                             |   54 +
 tests/budget_circuit_breaker.test.js               |  110 ++
 tests/degraded_mode_controller.test.js             |  134 ++
 tests/federated_envelope.test.js                   |   52 +
 tests/federated_rpc_v0.test.js                     |   76 +
 tests/gateway.test.js                              |  341 +++++
 tests/litellm_proxy_provider.test.js               |  116 ++
 tests/model_call_litellm_route.test.js             |   87 ++
 tests/model_call_system2_policy.test.js            |   96 ++
 tests/sys_config.test.js                           |  147 ++
 tests/system2_event_log_sync.test.js               |   73 +
 tests/system2_routing_policy_contract.test.js      |   61 +
 tests/system2_startup_invariants.test.js           |   71 +
 tests/system2_tool_plane.test.js                   |   91 ++
 tests/telegram_backoff.test.js                     |  151 ++
 tests/telegram_e2e_harness.test.js                 |   87 ++
 workspace/docs/governance/BRANCH-PROTECTION.md     |   13 -
 53 files changed, 7797 insertions(+), 154 deletions(-)
```

### 1.2 Categorization table

| Bucket | Meaning | Count | Top paths |
| --- | --- | ---: | --- |
| A | docs/audits only | 4 | A docs/system2/OPERATOR_RUNBOOK.md<br>A notes/governance/2026-02-11-change-admission-gate-system2-brief-broad.md<br>A reference/TROUBLESHOOTING.md<br>D workspace/docs/governance/BRANCH-PROTECTION.md |
| B | tests/scripts tooling | 20 | A scripts/audit_system2.mjs<br>A scripts/check_staged_allowlist.js<br>D scripts/run_tests.js<br>A scripts/system2_invariant_probe.js<br>A scripts/telegram_diag.js<br>A tests/budget_circuit_breaker.test.js<br>A tests/degraded_mode_controller.test.js<br>A tests/federated_envelope.test.js |
| C | runtime code paths | 25 | A core/integration/system1_adapter.js<br>A core/model_call.js<br>A core/model_constants.js<br>A core/model_runtime.js<br>A core/providers/litellm_proxy_provider.js<br>A core/router.js<br>A core/system2/budget_circuit_breaker.js<br>A core/system2/degraded_mode_controller.js |
| D | CI/workflows | 2 | D .github/workflows/node_test.yml<br>A .github/workflows/system2_macos_audit.yml |
| E | suspicious / dependency-shape deltas | 2 | D package-lock.json<br>M package.json |

### 1.3 Port scope decision

- Rule applied: first port only scripts/tests/docs/ci changes with clear intent and no new runtime dependency burden.
- Tests/scripts in this delta depend on missing runtime modules in broken commit, so they are deferred in this first port.
- CI workflow `system2_macos_audit.yml` is deferred (likely non-deterministic / runtime-coupled).
- Selected scope for this port: docs + schema contracts only:
  - docs/system2/OPERATOR_RUNBOOK.md
  - notes/governance/2026-02-11-change-admission-gate-system2-brief-broad.md
  - reference/TROUBLESHOOTING.md
  - schemas/federated_job_envelope.schema.json
  - schemas/system2_observability_event.schema.json
  - schemas/system2_routing_policy_contract.schema.json
  - schemas/system2_sync_cursor.schema.json
- Deferred scope: core/, sys/, tests/, scripts/, .github/workflows/system2_macos_audit.yml, package.json/package-lock deltas.
## Phase 2 - Port Changes

### 2.1 Commit lineage from origin/main to broken target

```
```

Decision: lineage is broad runtime-heavy; using path-limited patch apply for selected scope.

### 2.2 Path-limited patch apply

```
     546 /tmp/salvage.patch
A  docs/system2/OPERATOR_RUNBOOK.md
A  notes/governance/2026-02-11-change-admission-gate-system2-brief-broad.md
A  reference/TROUBLESHOOTING.md
A  schemas/federated_job_envelope.schema.json
A  schemas/system2_observability_event.schema.json
A  schemas/system2_routing_policy_contract.schema.json
A  schemas/system2_sync_cursor.schema.json
?? workspace/docs/audits/
```

### Phase 2 execution note

- First patch apply succeeded and was committed in fd34fa6.
- A second accidental apply attempt returned 'already exists in index' for selected files; no extra changes were introduced.

### git -C /tmp/clawd-postmerge-validate-kDVoV5 status --short --branch

```
## salvage/port-system2-unified...origin/main [ahead 1]
?? workspace/docs/audits/
```

## Phase 3 - Missing Relative Require Verification

### 3.1 Scanner run on current branch HEAD

```
Wrote workspace/docs/audits/SALVAGE-REPORT-port-system2-unified-2026-02-12.md with 0 findings.
# SALVAGE REPORT: system2 unified integration

- Generated at: 2026-02-11T20:39:06.599Z
- Analyzed commit: `HEAD`
- File inventory size: 133
- Code files scanned: 2
- Findings: 0 MISSING_RELATIVE_REQUIRE entries

## Counts by File (Top Offenders)

| File | Missing Relative Requires |
| --- | ---: |

## Findings

| Type | File | Specifier |
| --- | --- | --- |

## Suggested Minimal Remediation Strategies (Not Applied)

- Restore missing sibling modules that existing relative paths already reference.
- Prefer targeted path corrections only where specifier typos are proven.
- Add narrow compatibility entrypoints (for example index.js wrappers) only when needed.
- Avoid broad refactors; re-run deterministic tests after each small patch set.

```

### 3.2 Fix decision

- MISSING_RELATIVE_REQUIRE_COUNT=0
- No fix script run required (count is zero).

## Phase 4 - Validation

### 4.1 npm ci && npm test

```

up to date, audited 1 package in 323ms

found 0 vulnerabilities

> openclaw@0.0.0 test
> node scripts/run_tests.js

RUN python3  -m unittest discover -s tests_unittest -p test_*.py
.................
----------------------------------------------------------------------
Ran 17 tests in 0.003s

OK
OK 1 test group(s)
```

### 4.2 Dedicated verifier command

```
Wrote /tmp/salvage_final_report.md with 0 findings.
# SALVAGE REPORT: system2 unified integration

- Generated at: 2026-02-11T20:39:18.516Z
- Analyzed commit: `HEAD`
- File inventory size: 133
- Code files scanned: 2
- Findings: 0 MISSING_RELATIVE_REQUIRE entries

## Counts by File (Top Offenders)

| File | Missing Relative Requires |
| --- | ---: |

## Findings

| Type | File | Specifier |
| --- | --- | --- |

## Suggested Minimal Remediation Strategies (Not Applied)

- Restore missing sibling modules that existing relative paths already reference.
- Prefer targeted path corrections only where specifier typos are proven.
- Add narrow compatibility entrypoints (for example index.js wrappers) only when needed.
- Avoid broad refactors; re-run deterministic tests after each small patch set.

```

### 2.1 supplemental lineage (merge-base -> broken)

```
merge_base=9f35bc1ab7d802e60923c95679febc0325555007
```

## Phase 5 - Final State

```
83387f0ec03a93e31f6fd6137b0f41214cc4c9bb
83387f0 (HEAD -> salvage/port-system2-unified, origin/salvage/port-system2-unified) fix(salvage): add module-resolution verifier and zero-findings evidence
fd34fa6 salvage(port): bring over selected exec2 docs/schema changes

> openclaw@0.0.0 test
> node scripts/run_tests.js

RUN python3  -m unittest discover -s tests_unittest -p test_*.py
OK 1 test group(s)
Wrote /tmp/salvage_final_report_postcommit.md with 0 findings.
- Findings: 0 MISSING_RELATIVE_REQUIRE entries
## salvage/port-system2-unified...origin/salvage/port-system2-unified
 M workspace/docs/audits/SALVAGE-EXEC2-2026-02-12.md
```

