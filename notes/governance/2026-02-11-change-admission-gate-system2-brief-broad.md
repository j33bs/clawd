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
