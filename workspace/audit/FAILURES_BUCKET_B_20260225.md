# Bucket-B Verification Failures (2026-02-25)

## Commands + Exit Codes

- `bash workspace/scripts/verify_preflight.sh`
  Exit: 2
- `python3 -m unittest -v`
  Exit: 1
- `node --test`
  Exit: 1

## Failing Tests / Checks

### unittest (sample failing entries)
- `ERROR: test_append_only_ledger_grows_and_worker_completes (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_append_only_ledger_grows_and_worker_completes)`
- `ERROR: test_run_header_contains_required_fields (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_run_header_contains_required_fields)`
- `FAIL: test_verifier_passes_in_repo (tests_unittest.test_goal_identity_invariants.TestGoalIdentityInvariants.test_verifier_passes_in_repo)`
- `FAIL: test_active_inference_fallback_keeps_router_operational (tests_unittest.test_policy_router_active_inference_hook.TestPolicyRouterActiveInferenceHook.test_active_inference_fallback_keeps_router_operational)`
- `FAIL: test_openai_oauth_jwt_is_gated_before_network (tests_unittest.test_policy_router_oauth_gate.TestPolicyRouterOauthGate.test_openai_oauth_jwt_is_gated_before_network)`

### node --test failures
- `tests/freecompute_cloud.test.js`
- `tests/model_routing_no_oauth.test.js`
- `tests/provider_diag_coder_reason.test.js`

## Related vs Unrelated Evidence

1. Preflight failure is workspace drift based, not import/runtime failure from admitted files.
   - Evidence: `verify_preflight` tail reports `STOP (unrelated workspace drift detected)`.
   - Evidence: it flags many unrelated untracked paths (e.g., `.worktrees/`, `workspace/research/pdfs/*`, `workspace/tacti_dashboard.html`, multiple docs/memory files).
2. unittest and node failures are concentrated in existing router/local-exec/governance tests outside admitted Bucket-B files.
   - Evidence: failing unittest modules are under `tests_unittest/test_local_exec_plane_offline.py`, `tests_unittest/test_policy_router_*`, `tests_unittest/test_goal_identity_invariants.py`, `tests_unittest/test_witness_ledger.py`.
   - Evidence: node failures are in `tests/freecompute_cloud.test.js`, `tests/model_routing_no_oauth.test.js`, `tests/provider_diag_coder_reason.test.js`.
3. The admitted feature commit touched only Bucket-B module paths under `workspace/` (TACTI/memory/novelty tooling) and did not modify the failing test files or preflight script logic.
