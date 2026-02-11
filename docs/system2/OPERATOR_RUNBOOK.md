# System-2 Operator Runbook

## Purpose
Operate and verify the System-2 subsystem with reversible, evidence-backed checks.

## Primary Commands
- `node scripts/system2_invariant_probe.js`
- `node tests/system2_routing_policy_contract.test.js`
- `node tests/federated_envelope.test.js`
- `node tests/federated_rpc_v0.test.js`
- `node tests/system2_tool_plane.test.js`
- `node tests/system2_event_log_sync.test.js`
- `npm run audit:system2`

## Evidence Artifacts
- `reports/system2/system2_audit_evidence.json`
- `reports/ci/system2/system2_audit_evidence.json`
- `reports/system2/system2_audit_smoke.log`

## Rollback
1. Disable runtime flags:
   - `system2.feature_enabled = false`
   - `system2.federation_enabled = false`
   - `system2.tool_plane_enabled = false`
   - `system2.use_litellm_proxy = false`
2. Revert commits in reverse order:
   - `git revert <sha>`
3. Re-run:
   - `node scripts/verify_model_routing.js`
   - `node tests/local_fallback_routing.test.js`
   - `node tests/sys_acceptance.test.js`

## Notes
- Envelope signing uses env key `SYSTEM2_ENVELOPE_HMAC_KEY`.
- Tool plane is default-deny and read-only allowlist first.
- No secrets should be committed or logged in evidence outputs.
