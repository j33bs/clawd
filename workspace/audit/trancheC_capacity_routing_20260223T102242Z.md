# Tranche C - Capacity + Routing (20260223T102242Z)

## Phase 0 Baseline
$ git fetch origin
executed
$ git checkout -b codex/feat/tranche-c-20260223 origin/main
branch created from origin/main
$ git status --porcelain -uall
(no output; clean)
$ git rev-parse HEAD
728877a56c2beb1cce6d1f16c51983088b230a03
$ node -v
v22.22.0
$ python3 --version
Python 3.12.3

## Recon Findings
Control points located:
- `workspace/scripts/policy_router.py`
- `workspace/policy/llm_policy.json`
- `core/system2/inference/router.js`
- `core/system2/inference/provider_registry.js`
- `scripts/vllm_launch_coder.sh`
- `workspace/systemd/openclaw-vllm-coder.service`
- assistant launcher helper present: `scripts/system2/run_local_vllm.sh`

Context/routing notes:
- Policy router currently enforces `maxTokensPerRequest` (default 1024) and provider `maxInputChars`; this is the primary Python-side context guard.
- `workspace/policy/llm_policy.json` currently declares local assistant context capability `16384` tokens and local model `maxInputChars` of `4000` for assistant/coder.
- `scripts/vllm_launch_coder.sh` defaults `VLLM_CODER_MAX_MODEL_LEN=16384`.
- System2 Node registry already includes message compaction and context-aware routing (`core/system2/inference/provider_registry.js` + `router.js`), but Tranche C requested scope is centered on policy_router + policy controls and diagnostics exposure.

Uncertainty recorded:
- User stated origin/main includes Tranche B; fetched `origin/main` currently points to `728877a56c2beb1cce6d1f16c51983088b230a03` (Tranche A merge commit in prior audit trail). Proceeding from canonical fetched main.

## Phase 1 - Local Context Expansion + Guard
Implemented:
- `workspace/policy/llm_policy.json`
  - defaults:
    - `maxTokensPerRequest=32768`
    - `local_context_max_tokens_assistant=32768`
    - `local_context_max_tokens_coder=32768`
    - `local_context_soft_limit_tokens=24576`
    - `local_context_overflow_policy=compress`
  - local provider model max input chars raised to `131072` for assistant/coder.
  - local capabilities context windows set to `32768`.
- `workspace/scripts/policy_router.py`
  - added deterministic local context guard with policy-driven soft/hard limits
  - added structured context overflow (`CONTEXT_TOO_LARGE`) when local cannot proceed safely
  - added deterministic compression preserving constraints/headings/bullets/code fence boundaries
  - added event envelope emission: `context.compressed`
- launch defaults raised for local runtime helpers:
  - `scripts/vllm_launch_coder.sh` default `VLLM_CODER_MAX_MODEL_LEN=32768`
  - `scripts/system2/run_local_vllm.sh` default `VLLM_MAX_MODEL_LEN=32768`
- tests added:
  - `tests_unittest/test_policy_router_context_guard.py`

## Phase 2 - Task-Based Local-First Router + Remote Gate
Implemented:
- `workspace/scripts/policy_router.py`
  - added deterministic task classes via `classify_task_class(...)`:
    - `mechanical_execution`
    - `planning_synthesis`
    - `research_browse`
    - `code_generation_large`
  - planning routing now local-first when within local soft limit.
  - remote path is gated by policy/env (`remoteRoutingEnabled` + allowlist task classes) and existing budget/circuit checks.
  - added envelope emission: `route.decision` with task class/provider/reason/budget snapshot.
- `workspace/policy/llm_policy.json`
  - defaults include remote routing policy knobs:
    - `remoteRoutingEnabled=false`
    - `remoteAllowlistTaskClasses=[planning_synthesis,research_browse,code_generation_large]`
  - capability router code lane defaults moved local-first:
    - `codeProvider=local_vllm_coder`
    - `smallCodeProvider=local_vllm_assistant`
- tests:
  - updated `tests_unittest/test_policy_router_capability_classes.py`
  - added `tests_unittest/test_policy_router_task_router.py`

## Phase 3 - Diagnostics
Implemented:
- `scripts/system2/provider_diag.js`
  - reports context/routing policy markers:
    - `router_local_context_max_tokens_assistant`
    - `router_local_context_max_tokens_coder`
    - `router_local_context_soft_limit_tokens`
    - `router_local_context_overflow_policy`
    - `router_context_compression_enabled`
    - `router_remote_routing_enabled`
    - `router_remote_allowlist_task_classes`
  - reports budget state visibility:
    - `router_budget_state_loaded`, `router_budget_date`, token counters
- test update:
  - `tests/provider_diag_format.test.js`

## Verification Commands + Outputs
First targeted test run:
$ python3 -m unittest -v tests_unittest.test_policy_router_capability_classes tests_unittest.test_policy_router_context_guard tests_unittest.test_policy_router_task_router
Result: FAIL (2 failures)
- `test_context_guard_compresses_deterministically_over_soft_limit`: input was below soft limit (no compression expected).
- `test_overflow_uses_remote_only_when_enabled_and_budget_allows`: per-request cap in test fixture was too low for remote overflow scenario.

Smallest fixes applied:
- increase compression test payload into soft-limit overflow band.
- raise test fixture `maxTokensPerRequest` to permit overflow remote path.
- pin TACTI flags off in remote-overflow test path to avoid unrelated suppression side effects.

Final targeted python tests:
$ python3 -m unittest -v tests_unittest.test_policy_router_capability_classes tests_unittest.test_policy_router_context_guard tests_unittest.test_policy_router_task_router
Ran 13 tests in 1.279s
OK

Node diagnostics format test:
$ node tests/provider_diag_format.test.js
PASS provider_diag includes grep-friendly providers_summary section
provider_diag_format tests complete

Additional regression check:
$ node tests/provider_diag_never_unknown.test.js
PASS journal unavailable maps to UNAVAILABLE and never UNKNOWN
PASS journal marker maps to DEGRADED reason from marker
PASS journal with no marker maps to NO_BLOCK_MARKER and DOWN
provider_diag_never_unknown tests complete

Smoke:
$ node scripts/system2/provider_diag.js || true
Key markers observed:
- `router_local_context_max_tokens_assistant=32768`
- `router_local_context_soft_limit_tokens=24576`
- `router_context_compression_enabled=true`
- `router_remote_routing_enabled=false`
- `router_budget_state_loaded=false` (no local budget file in this clean worktree)

## Rollback
- `git revert <tranche-c commit sha>` for each commit in reverse order.
- No host-only state changes were committed in this tranche.

## Residual Uncertainties
- fetched `origin/main` did not include prior Tranche B merge in this environment; this tranche was implemented on the canonical fetched head (`728877a...`).
- runtime assistant vLLM health on `:8001` remains host-dependent and outside these repo changes.
