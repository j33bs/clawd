# PR: C_Lawd Full Remediation (System-2)

## What Changed
- Removed integrity one-shot bypass; requests now re-verify governance anchors every enforcement call.
- Moved Gemini API key transport from URL query string to `x-goog-api-key` header.
- Added audit hash-chain verification on sink load with fail-closed tamper detection.
- Added governance log enforcement guard (`workspace/scripts/verify_governance_log.sh`) and wired it into CI/regression.
- Hardened file secrets backend passphrase contract: secure file path preferred, env passphrase blocked outside dev/test by default.
- Replaced workspace boundary `.startsWith()` check with realpath containment validation.
- Removed stale `workspace/BOOTSTRAP.md` and triaged untracked artifact-loss risk with explicit `.gitignore` hygiene entries.
- Added OAuth gate in policy router to fail closed for OpenAI OAuth JWTs hitting unsupported endpoint flow.
- Removed tracked Source UI token and hard-coded root/machine-specific service assumptions; switched to env-file template pattern.
- Scrubbed scanner-noise fixtures to non-secret placeholders while preserving redaction test semantics.

## Why
- Prevent integrity drift from being masked after first pass in long-lived processes.
- Eliminate credential leakage via URLs (logs/proxies/referers) and tracked service units.
- Convert audit chain from write-only metadata into an enforceable tamper-evident control.
- Enforce governance process mechanically instead of relying on operator discipline.
- Keep secret handling cross-platform and production-safe without weakening fail-closed behavior.

## Verification
Targeted remediations were validated on the remediation branch via:
- `node tests/integrity_guard.test.js` (PASS)
- `node tests/freecompute_cloud.test.js` (PASS)
- `node tests/audit_sink_hash_chain.test.js` (PASS)
- `bash workspace/scripts/verify_governance_log.sh` (PASS)
- `node tests/secrets_bridge.test.js` + `node tests/secrets_cli_exec.test.js` (PASS)
- `node tests/tool_governance.test.js` (PASS)
- `python3 -m unittest -q tests_unittest.test_policy_router_oauth_gate` (PASS)
- `node tests/redact_audit_evidence.test.js` + `node tests/system2_evidence_bundle.test.js` + `npm run check:redaction-fixtures` (PASS)

Evidence docs:
- `/Users/heathyeager/clawd/workspace/audit/c_lawd_full_audit_remediation_20260221T070817Z.md`
- `/Users/heathyeager/clawd/workspace/audit/c_lawd_pr_merge_and_followups_20260221T080418Z.md`

## Known Pre-Existing Failing Gates (Not Introduced By This PR)
Failure excerpts captured during full-suite runs:
- `FAIL: repo-root governance file diverges from canonical: SOUL.md`
- `AssertionError [ERR_ASSERTION]: policy.providers must not include openai-codex`
- `✗ FAIL: openclaw config not found for provider gating check`
- `FAIL: agents/main/agent/models.json: groq.enabled must be false`
- `FAIL: agents/main/agent/models.json: groq.apiKey must be empty (no secrets)`

Root-cause pointers:
- SOUL canonical mirror check: `workspace/scripts/verify_goal_identity_invariants.py:18`, `workspace/scripts/verify_goal_identity_invariants.py:183`
- Routing assertion: `tests/model_routing_no_oauth.test.js:84`
- Regression config gate: `workspace/scripts/regression.sh:209`, `workspace/scripts/regression.sh:263`
- Groq verifier expectations: `workspace/scripts/verify_security_config.sh:21`, `workspace/scripts/verify_security_config.sh:23`, `workspace/scripts/verify_security_config.sh:46`

## Follow-Up Branch Plan
1. `fix/canonical-soul-drift-20260221T080616Z`
Scope: resolve SOUL canonical drift so goal/identity invariant test reflects intended canonical source.
2. `fix/regression-bootstrap-config-20260221T080905Z`
Scope: make regression config check aware of bootstrap contract (`OPENCLAW_CONFIG_PATH` / ephemeral config) instead of hard fail on missing tracked config.
3. `fix/groq-policy-alignment-20260221T081156Z`
Scope: resolve Groq verifier/model policy mismatch with explicit policy intent and verifier alignment.
