# Dali Safe Surface + Intent Gates Audit

- UTC timestamp: 2026-02-21T23:40:03Z
- Branch: codex/fix-safe-surface-and-intent-gates-20260222
- Initial HEAD: 04e6f6310a316510ed2258314e534e0698dfdf01

## Initial Worktree
```text
 M workspace/policy/llm_policy.json
 M workspace/scripts/policy_router.py
 M workspace/scripts/rebuild_runtime_openclaw.sh
 M workspace/scripts/telegram_hardening_helpers.js
 M workspace/scripts/verify_policy_router.sh
 M workspace/state/tacti_cr/events.jsonl
?? docs/GPU_SETUP.md
?? scripts/vllm_prefix_warmup.js
?? tests/safe_error_surface.test.js
?? tests_unittest/test_discord_thin_adapter.py
?? tests_unittest/test_mcporter_tool_plane.py
?? tests_unittest/test_policy_router_capability_classes.py
?? workspace/NOVELTY_LOVE_ALIGNMENT_RECS.md
?? workspace/NOVELTY_LOVE_ALIGNMENT_TODO.md
?? workspace/artifacts/itc/events/itc_events.jsonl
?? workspace/audit/dali_cbp_discord_vllm_redaction_20260221T232545Z.md
?? workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md
?? workspace/audit/dali_vllm_duplicate_audit_20260221T204359Z.md
?? workspace/docs/ops/DISCORD_THIN_ADAPTER.md
?? workspace/policy/llm_policy.json.bak.20260221T231425Z
?? workspace/scripts/discord_adapter.py
?? workspace/scripts/gateway_router.py
?? workspace/scripts/mcporter_tool_plane.py
?? workspace/scripts/policy_router.py.bak.20260221T231425Z
?? workspace/scripts/rebuild_runtime_openclaw.sh.bak.20260221T231425Z
?? workspace/scripts/safe_error_surface.js
?? workspace/scripts/safe_error_surface.py
?? workspace/scripts/telegram_hardening_helpers.js.bak.20260221T231425Z
?? workspace/scripts/verify_policy_router.sh.bak.20260221T231425Z
```

## Phase 1 Backups

- Backup timestamp: 20260221T234009Z
```text
tests/safe_error_surface.test.js.bak.20260221T234009Z
tests_unittest/test_policy_router_capability_classes.py.bak.20260221T234009Z
workspace/scripts/policy_router.py.bak.20260221T234009Z
workspace/scripts/safe_error_surface.js.bak.20260221T234009Z
workspace/scripts/safe_error_surface.py.bak.20260221T234009Z
```

## Phase 4 Targeted Verification

```bash
node tests/safe_error_surface.test.js
```

```text
PASS redact hides bearer/api keys/cookies
PASS safe envelope keeps stable public surface
PASS safe envelope redacts malicious public message text
PASS adapter error text excludes internal log hints
```

```bash
python3 -m unittest tests_unittest.test_safe_error_surface -v
```

```text
test_envelope_redacts_malicious_public_message (tests_unittest.test_safe_error_surface.TestSafeErrorSurface.test_envelope_redacts_malicious_public_message) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```

```bash
python3 -m unittest tests_unittest.test_policy_router_capability_classes -v
```

```text
test_classifier_mechanical_examples (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_classifier_mechanical_examples) ... ok
test_classifier_negative_guards_prevent_overcapture (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_classifier_negative_guards_prevent_overcapture) ... ok
test_explain_and_apply_patch_routes_to_mechanical_provider (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_explain_and_apply_patch_routes_to_mechanical_provider) ... ok
test_mechanical_execution_prefers_local_vllm (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_mechanical_execution_prefers_local_vllm) ... ok
test_planning_synthesis_prefers_cloud (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_planning_synthesis_prefers_cloud) ... ok
test_router_logs_request_id_latency_outcome (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_router_logs_request_id_latency_outcome) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.003s

OK
```

```bash
bash workspace/scripts/verify_policy_router.sh
```

```text
Traceback (most recent call last):
  File "<stdin>", line 415, in <module>
  File "<stdin>", line 410, in main
  File "<stdin>", line 339, in test_capability_routing_precedence_and_targets
AssertionError: {'provider': 'openai_gpt52_chat', 'model': 'gpt-5.2-chat-latest', 'reason_code': None}
```

## Phase 4 Verification (Post-Fix Rerun)

```bash
node tests/safe_error_surface.test.js
```

```text
PASS redact hides bearer/api keys/cookies
PASS safe envelope keeps stable public surface
PASS safe envelope redacts malicious public message text
PASS adapter error text excludes internal log hints
```

```bash
python3 -m unittest tests_unittest.test_safe_error_surface -v
```

```text
test_envelope_redacts_malicious_public_message (tests_unittest.test_safe_error_surface.TestSafeErrorSurface.test_envelope_redacts_malicious_public_message) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```

```bash
python3 -m unittest tests_unittest.test_policy_router_capability_classes -v
```

```text
test_classifier_mechanical_examples (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_classifier_mechanical_examples) ... ok
test_classifier_negative_guards_prevent_overcapture (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_classifier_negative_guards_prevent_overcapture) ... ok
test_explain_and_apply_patch_routes_to_mechanical_provider (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_explain_and_apply_patch_routes_to_mechanical_provider) ... ok
test_mechanical_execution_prefers_local_vllm (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_mechanical_execution_prefers_local_vllm) ... ok
test_planning_synthesis_prefers_cloud (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_planning_synthesis_prefers_cloud) ... ok
test_router_logs_request_id_latency_outcome (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_router_logs_request_id_latency_outcome) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.003s

OK
```

```bash
bash workspace/scripts/verify_policy_router.sh
```

```text
ok
```



## Phase 5 Evidence Update (2026-02-21T23:49:25Z)

### Diff Summary

```text
 tests/safe_error_surface.test.js                   |  66 ++++
 .../test_policy_router_capability_classes.py       | 127 +++++++
 tests_unittest/test_safe_error_surface.py          |  27 ++
 ...i_safe_surface_intent_gates_20260221T234003Z.md | 183 ++++++++++
 workspace/scripts/policy_router.py                 | 404 ++++++++++++++-------
 workspace/scripts/safe_error_surface.js            | 100 +++++
 workspace/scripts/safe_error_surface.py            | 111 ++++++
 7 files changed, 883 insertions(+), 135 deletions(-)
```

### Key Before/After Excerpts

```text
Python safe envelope
Before (workspace/scripts/safe_error_surface.py.bak.20260221T234700Z):
) -> dict[str, Any]:
    summary = str(debug_summary or "").strip().lower()
    return {
        "public_message": str(public_message),
        "error_code": str(error_code),
        "request_id": str(request_id or next_request_id("err")),
        "occurred_at": occurred_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
After (workspace/scripts/safe_error_surface.py):
) -> dict[str, Any]:
    summary = str(debug_summary or "").strip().lower()
    return {
        "public_message": _redact_text(public_message),
        "error_code": str(error_code),
        "request_id": str(request_id or next_request_id("err")),
        "occurred_at": occurred_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),

JS safe envelope
Before (workspace/scripts/safe_error_surface.js.bak.20260221T234700Z):
} = {}) {
  const normalizedDebug = String(debugSummary || '').trim().toLowerCase();
  return {
    public_message: String(publicMessage),
    error_code: String(errorCode),
    request_id: requestId ? String(requestId) : nextRequestId('err'),
    occurred_at: occurredAt || new Date().toISOString(),
After (workspace/scripts/safe_error_surface.js):
} = {}) {
  const normalizedDebug = String(debugSummary || '').trim().toLowerCase();
  return {
    public_message: _redactString(publicMessage),
    error_code: String(errorCode),
    request_id: requestId ? String(requestId) : nextRequestId('err'),
    occurred_at: occurredAt || new Date().toISOString(),

Policy router mechanical/planning gates
Before (workspace/scripts/policy_router.py.bak.20260221T234700Z):
1084:        mechanical_keywords = [
1086:            "code",
1087:            "implement",
1096:            "patch",
1111:        has_mechanical = any(keyword in lower for keyword in mechanical_keywords)
1161:        if capability_class in {"mechanical_execution", "hybrid"}:
After (workspace/scripts/policy_router.py):
806:_INTENT_NEGATIVE_GUARDS = [
821:def classify_intent(text: str) -> str:
829:    if any(rx.search(normalized) for rx in _INTENT_NEGATIVE_GUARDS) and not has_action_word:
851:    if any(rx.search(normalized) for rx in _INTENT_NEGATIVE_GUARDS) and not has_action_word:
1182:        if capability_class == "mechanical_execution":
1194:            if not _has_strong_planning_signal(text):
```

### Verification Outputs

```bash
node tests/safe_error_surface.test.js
```
```text
PASS redact hides bearer/api keys/cookies
PASS safe envelope keeps stable public surface
PASS safe envelope redacts malicious public message text
PASS adapter error text excludes internal log hints
```

```bash
python3 -m unittest tests_unittest.test_policy_router_capability_classes -v
```
```text
test_classifier_mechanical_examples (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_classifier_mechanical_examples) ... ok
test_classifier_negative_guards_prevent_overcapture (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_classifier_negative_guards_prevent_overcapture) ... ok
test_explain_and_apply_patch_routes_to_mechanical_provider (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_explain_and_apply_patch_routes_to_mechanical_provider) ... ok
test_mechanical_execution_prefers_local_vllm (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_mechanical_execution_prefers_local_vllm) ... ok
test_planning_synthesis_prefers_cloud (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_planning_synthesis_prefers_cloud) ... ok
test_router_logs_request_id_latency_outcome (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_router_logs_request_id_latency_outcome) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.003s

OK
```

```bash
python3 -m unittest tests_unittest.test_safe_error_surface -v
```
```text
test_envelope_redacts_malicious_public_message (tests_unittest.test_safe_error_surface.TestSafeErrorSurface.test_envelope_redacts_malicious_public_message) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```

```bash
bash workspace/scripts/verify_policy_router.sh
```
```text
ok
```

### Current Worktree Snapshot

```text
A  tests/safe_error_surface.test.js
A  tests_unittest/test_policy_router_capability_classes.py
A  tests_unittest/test_safe_error_surface.py
AM workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md
 M workspace/policy/llm_policy.json
M  workspace/scripts/policy_router.py
 M workspace/scripts/rebuild_runtime_openclaw.sh
A  workspace/scripts/safe_error_surface.js
A  workspace/scripts/safe_error_surface.py
 M workspace/scripts/telegram_hardening_helpers.js
 M workspace/scripts/verify_policy_router.sh
 M workspace/state/tacti_cr/events.jsonl
?? docs/GPU_SETUP.md
?? scripts/vllm_prefix_warmup.js
?? tests/safe_error_surface.test.js.bak.20260221T234009Z
?? tests/safe_error_surface.test.js.bak.20260221T234700Z
?? tests_unittest/test_discord_thin_adapter.py
?? tests_unittest/test_mcporter_tool_plane.py
?? tests_unittest/test_policy_router_capability_classes.py.bak.20260221T234009Z
?? tests_unittest/test_policy_router_capability_classes.py.bak.20260221T234700Z
?? tests_unittest/test_safe_error_surface.py.bak.20260221T234700Z
?? workspace/NOVELTY_LOVE_ALIGNMENT_RECS.md
?? workspace/NOVELTY_LOVE_ALIGNMENT_TODO.md
?? workspace/artifacts/itc/events/itc_events.jsonl
?? workspace/audit/dali_cbp_discord_vllm_redaction_20260221T232545Z.md
?? workspace/audit/dali_vllm_duplicate_audit_20260221T204359Z.md
?? workspace/docs/ops/DISCORD_THIN_ADAPTER.md
?? workspace/policy/llm_policy.json.bak.20260221T231425Z
?? workspace/scripts/discord_adapter.py
?? workspace/scripts/gateway_router.py
?? workspace/scripts/mcporter_tool_plane.py
?? workspace/scripts/policy_router.py.bak.20260221T231425Z
?? workspace/scripts/policy_router.py.bak.20260221T234009Z
?? workspace/scripts/policy_router.py.bak.20260221T234700Z
?? workspace/scripts/rebuild_runtime_openclaw.sh.bak.20260221T231425Z
?? workspace/scripts/safe_error_surface.js.bak.20260221T234009Z
?? workspace/scripts/safe_error_surface.js.bak.20260221T234700Z
?? workspace/scripts/safe_error_surface.py.bak.20260221T234009Z
?? workspace/scripts/safe_error_surface.py.bak.20260221T234700Z
?? workspace/scripts/telegram_hardening_helpers.js.bak.20260221T231425Z
?? workspace/scripts/verify_policy_router.sh.bak.20260221T231425Z
```

### Rollback Plan

1. Revert commit: git revert <commit_sha>
2. Or restore backups and re-run verification:
   - cp workspace/scripts/safe_error_surface.py.bak.20260221T234700Z workspace/scripts/safe_error_surface.py
   - cp workspace/scripts/safe_error_surface.js.bak.20260221T234700Z workspace/scripts/safe_error_surface.js
   - cp workspace/scripts/policy_router.py.bak.20260221T234700Z workspace/scripts/policy_router.py
   - cp tests/safe_error_surface.test.js.bak.20260221T234700Z tests/safe_error_surface.test.js
   - cp tests_unittest/test_policy_router_capability_classes.py.bak.20260221T234700Z tests_unittest/test_policy_router_capability_classes.py
   - cp tests_unittest/test_safe_error_surface.py.bak.20260221T234700Z tests_unittest/test_safe_error_surface.py
   - bash workspace/scripts/verify_policy_router.sh

### Final Staged Diff Summary (2026-02-21T23:50:51Z)

```text
 tests/safe_error_surface.test.js                   |  56 +++
 .../test_policy_router_capability_classes.py       | 111 ++++++
 tests_unittest/test_safe_error_surface.py          |  27 ++
 ...i_safe_surface_intent_gates_20260221T234003Z.md | 336 ++++++++++++++++++
 workspace/scripts/policy_router.py                 | 381 +++++++++++++--------
 workspace/scripts/safe_error_surface.js            | 100 ++++++
 workspace/scripts/safe_error_surface.py            | 111 ++++++
 7 files changed, 987 insertions(+), 135 deletions(-)
```
