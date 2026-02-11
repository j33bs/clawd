# Change Admission Gate - system2 brief broad implementation (2026-02-11)

## design brief
Implement the System-2 design brief as an additive and reversible subsystem with default-off feature flags, stable schemas/contracts, local-adapter federation, and auditable rollout gates.

## evidence pack
- Baseline checks before implementation:
  - `node scripts/verify_model_routing.js`
  - `node tests/local_fallback_routing.test.js`
  - `node tests/sys_acceptance.test.js`
- Known pre-existing blocker recorded:
  - `node tests/audit_retention.test.js` failing in current baseline.
- Workstream isolated in `codex/system2-brief-broad` worktree branch.

## rollback plan
Revert subsystem commits in reverse order using `git revert <sha>`. Disable System-2 flags in config as first-line kill switch before code rollback.

## budget envelope
Scope limited to additive modules under `core/system2`, provider adapter, config/schema extensions, tests, and System-2 docs/scripts. No architectural rewrites or contract-breaking changes.

## expected roi
Provides peer-gateway readiness for System-2 with federated RPC contracts, routing-policy transparency, offline-first event durability, and governance-aligned observability.

## kill-switch
Disable:
- `system2.feature_enabled`
- `system2.federation_enabled`
- `system2.tool_plane_enabled`
- `system2.use_litellm_proxy`

Then revert latest System-2 commit if further rollback is required.

## post-mortem
If regressions occur, record failing command, affected subsystem, rollback SHA, and corrective follow-up before re-attempting rollout.

## phase 2 evidence update
- Added `system2` config contract to:
  - `sys/config/defaults.js`
  - `sys/config/config.schema.json`
  - `sys/config.toml`
  - `sys/config.toml.example`
- Added startup invariant probe:
  - `core/system2/startup_invariants.js`
  - `scripts/system2_invariant_probe.js`
- Added tests:
  - `tests/system2_startup_invariants.test.js`
  - updated `tests/sys_config.test.js`
- Verification run:
  - `node scripts/system2_invariant_probe.js`
  - `node tests/sys_config.test.js`
  - `node tests/system2_startup_invariants.test.js`

## phase 3 evidence update
- Added routing policy contract:
  - `core/system2/routing_policy_contract.js`
  - `schemas/system2_routing_policy_contract.schema.json`
- Integrated policy gate into `core/model_call.js` (additive, env-guarded via `OPENCLAW_SYSTEM2_POLICY_ENFORCE=1`).
- Added tests:
  - `tests/system2_routing_policy_contract.test.js`
  - `tests/model_call_system2_policy.test.js`
- Verification run:
  - `node tests/system2_routing_policy_contract.test.js`
  - `node tests/model_call_system2_policy.test.js`
  - `node scripts/verify_model_routing.js`
  - `node tests/local_fallback_routing.test.js`
  - `node tests/sys_acceptance.test.js`

## phase 4 evidence update
- Added LiteLLM provider adapter:
  - `core/providers/litellm_proxy_provider.js`
- Runtime/router integration (feature-flagged):
  - `core/model_runtime.js`
  - `core/router.js`
- Added tests:
  - `tests/litellm_proxy_provider.test.js`
  - `tests/model_call_litellm_route.test.js`
- Verification run:
  - `node tests/litellm_proxy_provider.test.js`
  - `node tests/model_call_litellm_route.test.js`
  - `node scripts/verify_model_routing.js`
  - `node tests/local_fallback_routing.test.js`
  - `node tests/sys_acceptance.test.js`

## phase 5 evidence update
- Added federated envelope and RPC modules:
  - `core/system2/federated_envelope.js`
  - `core/system2/federated_rpc_v0.js`
  - `core/integration/system1_adapter.js`
- Added schema:
  - `schemas/federated_job_envelope.schema.json`
- Added tests:
  - `tests/federated_envelope.test.js`
  - `tests/federated_rpc_v0.test.js`
- Verification run:
  - `node tests/federated_envelope.test.js`
  - `node tests/federated_rpc_v0.test.js`
  - `node scripts/verify_model_routing.js`
  - `node tests/local_fallback_routing.test.js`
  - `node tests/sys_acceptance.test.js`

## phase 6 evidence update
- Added read-only tool plane host:
  - `core/system2/tool_plane.js`
- Tool allowlist hash remains enforced by startup invariants (`scripts/system2_invariant_probe.js`).
- Added tests:
  - `tests/system2_tool_plane.test.js`
- Verification run:
  - `node tests/system2_tool_plane.test.js`
  - `node scripts/verify_model_routing.js`
  - `node tests/local_fallback_routing.test.js`
  - `node tests/sys_acceptance.test.js`
