# SALVAGE Runtime Slice Audit (2026-02-12)

Mode: CBP-governed execution.
Objective: port one small runtime/core slice from 9f35bc1 onto origin/main safely.

## Phase 0 - Setup

### git -C /tmp/clawd-postmerge-validate-kDVoV5 fetch --all --prune

```
```

### git -C /tmp/clawd-postmerge-validate-kDVoV5 checkout -b salvage/runtime-slice-001 origin/main

```
Switched to a new branch 'salvage/runtime-slice-001'
branch 'salvage/runtime-slice-001' set up to track 'origin/main'.
```

### Branch reuse decision

```
* salvage/runtime-slice-001              537092d [origin/main] docs(governance): add branch protection follow-up note
```

Decision: reuse local branch salvage/runtime-slice-001 (unpublished, at base SHA, tracking origin/main).

### git -C /tmp/clawd-postmerge-validate-kDVoV5 checkout salvage/runtime-slice-001

```
Already on 'salvage/runtime-slice-001'
Your branch is up to date with 'origin/main'.
```

### Baseline metadata

```
537092d61aa9eef841e35aed9272d04eea39737d
v25.6.0
11.8.0
```

### Baseline npm ci && npm test

```

up to date, audited 1 package in 310ms

found 0 vulnerabilities

> openclaw@0.0.0 test
> node scripts/run_tests.js

RUN python3  -m unittest discover -s tests_unittest -p test_*.py
.................
----------------------------------------------------------------------
Ran 17 tests in 0.002s

OK
OK 1 test group(s)
```

## Phase 1 - Select One Runtime Slice

### 1.1 Full delta (BASE vs BROKEN)

```
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
```

### 1.2 Runtime/core shortlist

```
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
A	scripts/audit_system2.mjs
A	scripts/check_staged_allowlist.js
D	scripts/run_tests.js
A	scripts/system2_invariant_probe.js
A	scripts/telegram_diag.js
A	sys/config.toml
A	sys/config.toml.example
A	sys/config/config.schema.json
A	sys/config/defaults.js
```

### 1.3 Grouped runtime shortlist

| Group | Count | Sample paths |
| --- | ---: | --- |
| core/system2/* | 10 | A core/system2/budget_circuit_breaker.js<br>A core/system2/degraded_mode_controller.js<br>A core/system2/event_log.js<br>A core/system2/federated_envelope.js<br>A core/system2/federated_rpc_v0.js |
| core/* | 5 | A core/model_call.js<br>A core/model_constants.js<br>A core/model_runtime.js<br>A core/router.js<br>A core/telegram_client.js |
| scripts/* | 5 | A scripts/audit_system2.mjs<br>A scripts/check_staged_allowlist.js<br>D scripts/run_tests.js<br>A scripts/system2_invariant_probe.js<br>A scripts/telegram_diag.js |
| sys/* | 2 | A sys/config.toml<br>A sys/config.toml.example |
| sys/config/* | 2 | A sys/config/config.schema.json<br>A sys/config/defaults.js |
| core/integration/* | 1 | A core/integration/system1_adapter.js |
| core/providers/* | 1 | A core/providers/litellm_proxy_provider.js |

### 1.3 Slice candidates and selection

- Candidate A: budget breaker primitive
  - runtime: core/system2/budget_circuit_breaker.js
  - test: tests/budget_circuit_breaker.test.js
  - coupling: no relative imports in runtime file; deterministic unit test present.
- Candidate B: degraded mode controller
  - runtime: core/system2/degraded_mode_controller.js
  - test: tests/degraded_mode_controller.test.js
  - coupling: low, but mode semantics overlap broader system2 behaviors.
- Candidate C: routing policy contract
  - runtime: core/system2/routing_policy_contract.js + core/model_constants.js
  - test: tests/system2_routing_policy_contract.test.js
  - coupling: medium (depends on model constants).

Selected slice: Candidate A (budget breaker primitive), because it is the smallest coherent runtime/core slice (2 files including test), self-contained, and deterministic under npm test.
## Phase 2 - Port Slice

### 2.1 Create path-limited patch

```
     282 /tmp/runtime_slice_001.patch
```

### 2.2 Apply patch to salvage/runtime-slice-001

```
A  core/system2/budget_circuit_breaker.js
A  tests/budget_circuit_breaker.test.js
?? workspace/docs/audits/
```

### Phase 2 execution note

- Patch apply executed once during evidence capture and staged the selected slice files.
- A duplicate apply invocation returned 'already exists in index' and was a no-op; commit content remained correct.

## Phase 3 - Fail-Closed Module Resolution Gate

### 3.1 npm ci && npm test

```

up to date, audited 1 package in 306ms

found 0 vulnerabilities

> openclaw@0.0.0 test
> node scripts/run_tests.js

RUN python3  -m unittest discover -s tests_unittest -p test_*.py
.................
----------------------------------------------------------------------
Ran 17 tests in 0.004s

OK
RUN node tests/budget_circuit_breaker.test.js
PASS starts in closed state with zero usage
PASS records usage and decrements remaining
PASS trips on token cap exceeded
PASS trips on call cap exceeded
PASS rejects usage when open
PASS canProceed returns false when open
PASS canProceed returns false when estimate exceeds remaining
PASS reset restores closed state
PASS reset with new caps
budget_circuit_breaker tests complete
OK 2 test group(s)
```

### 3.2 Missing-requires scan on HEAD

```
Wrote /tmp/clawd-postmerge-validate-kDVoV5/workspace/docs/audits/SALVAGE-RUNTIME-SLICE-001-REPORT-2026-02-12.md with 0 findings.
# SALVAGE REPORT: system2 unified integration

- Generated at: 2026-02-11T21:08:19.028Z
- Analyzed commit: `80d17fdc3a441329ea2e3db6cd2ce4201b84fb92`
- File inventory size: 128
- Code files scanned: 4
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

## Phase 4 - Optional Micro-Test

- Not needed: slice included deterministic upstream unit test (tests/budget_circuit_breaker.test.js).

## Phase 5 - Output State

```
80d17fdc3a441329ea2e3db6cd2ce4201b84fb92
80d17fd (HEAD -> salvage/runtime-slice-001) salvage(runtime): port slice-001 from 9f35bc1 (path-limited)
537092d (origin/main, origin/docs/governance-branch-protection-note, origin/HEAD, main, docs/governance-branch-protection-note) docs(governance): add branch protection follow-up note
ff4402d (tag: safety/pre-nextsteps-branchE-20260212062039, origin/ci/node-test-gate, ci/node-test-gate) ci(test): add deterministic node npm ci/npm test gate
```

