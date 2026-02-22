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


## Phase 5B Correction Pass (2026-02-21T23:54:03Z)

- Detected post-commit mismatch: redaction/classifier edits were not present in committed files.
- Applied corrective minimal diffs and re-verified all targeted tests.

### Correction Backups

- workspace/scripts/safe_error_surface.py.bak.20260221T235149Z
- workspace/scripts/safe_error_surface.js.bak.20260221T235149Z
- workspace/scripts/policy_router.py.bak.20260221T235149Z
- tests/safe_error_surface.test.js.bak.20260221T235149Z
- tests_unittest/test_policy_router_capability_classes.py.bak.20260221T235149Z
- tests_unittest/test_safe_error_surface.py.bak.20260221T235149Z
- workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md.bak.20260221T235149Z

### Corrected Line Evidence

```text
workspace/scripts/safe_error_surface.py:76 -> "public_message": _redact_text(public_message)
workspace/scripts/safe_error_surface.js:58 -> public_message: _redactString(publicMessage)
workspace/scripts/policy_router.py:821 -> def classify_intent(text: str) -> str
workspace/scripts/policy_router.py:829 -> negative guard applies only when no action word
workspace/scripts/policy_router.py:1182 -> if capability_class == "mechanical_execution"
workspace/scripts/policy_router.py:1194 -> if not _has_strong_planning_signal(text): return None
tests/safe_error_surface.test.js:44 -> malicious publicMessage redaction test
tests_unittest/test_policy_router_capability_classes.py:109 -> planning guard tests
tests_unittest/test_policy_router_capability_classes.py:114 -> mechanical examples
tests_unittest/test_policy_router_capability_classes.py:119 -> explain+apply patch mechanical routing
```

### Correction Verification Outputs

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

## Phase 0 Quiesce + Baseline (Clean-Rebuild Session)

timestamp_utc=2026-02-22T00:10:55Z
branch=codex/fix-safe-surface-and-intent-gates-20260222-clean
head=aee1ca93516ff7ed887f17dc67ba3f3025771198

systemctl/pgrep quiesce evidence:
== systemctl --user status openclaw-gateway.service ==

== systemctl --user stop openclaw-gateway.service ==

== pgrep -af vllm|ollama|openclaw|gateway|watch|nodemon|pytest|node --watch ==
179 [watchdogd]
3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
17770 openclaw-gateway
39315 /bin/bash -c set -euo pipefail mkdir -p /tmp/codex_safe_surface_clean {   echo '== systemctl --user status openclaw-gateway.service =='   systemctl --user status openclaw-gateway.service || true   echo   echo '== systemctl --user stop openclaw-gateway.service =='   systemctl --user stop openclaw-gateway.service || true   echo   echo '== pgrep -af vllm|ollama|openclaw|gateway|watch|nodemon|pytest|node --watch =='   pgrep -af 'vllm|ollama|openclaw|gateway|watch|nodemon|pytest|node --watch' || true } > /tmp/codex_safe_surface_clean/phase0_quiesce.txt cat /tmp/codex_safe_surface_clean/phase0_quiesce.txt

stop/kill actions evidence:
== pkill -x openclaw-gateway ==

== pgrep -af openclaw-gateway ==
39377 openclaw-gateway
39404 /bin/bash -c set -euo pipefail {   echo '== pkill -x openclaw-gateway =='   pkill -x openclaw-gateway || true   sleep 1   echo   echo '== pgrep -af openclaw-gateway =='   pgrep -af openclaw-gateway || true   echo   echo '== pgrep -af vllm =='   pgrep -af vllm || true } > /tmp/codex_safe_surface_clean/phase0_quiesce_stop.txt cat /tmp/codex_safe_surface_clean/phase0_quiesce_stop.txt

== pgrep -af vllm ==
3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
39404 /bin/bash -c set -euo pipefail {   echo '== pkill -x openclaw-gateway =='   pkill -x openclaw-gateway || true   sleep 1   echo   echo '== pgrep -af openclaw-gateway =='   pgrep -af openclaw-gateway || true   echo   echo '== pgrep -af vllm =='   pgrep -af vllm || true } > /tmp/codex_safe_surface_clean/phase0_quiesce_stop.txt cat /tmp/codex_safe_surface_clean/phase0_quiesce_stop.txt

== kill exact openclaw-gateway PID(s) via pgrep -f ^openclaw-gateway$ ==
pids=39377

== pgrep -af openclaw-gateway ==
39449 /bin/bash -c set -euo pipefail {   echo '== kill exact openclaw-gateway PID(s) via pgrep -f ^openclaw-gateway$ =='   PIDS=$(pgrep -f '^openclaw-gateway$' || true)   if [ -n "${PIDS}" ]; then     echo "pids=${PIDS}"     kill ${PIDS} || true     sleep 1   else     echo 'pids=(none)'   fi   echo   echo '== pgrep -af openclaw-gateway =='   pgrep -af openclaw-gateway || true } > /tmp/codex_safe_surface_clean/phase0_quiesce_kill_gateway.txt cat /tmp/codex_safe_surface_clean/phase0_quiesce_kill_gateway.txt

baseline repository state from source workspace:
date_utc=2026-02-22T00:00:44Z
branch=codex/fix-safe-surface-and-intent-gates-20260222
head=7480b24da4e0ac8994f28acd47eb4891ccc8e4db

[git status --porcelain -uall]
 M workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md
 M workspace/policy/llm_policy.json
 M workspace/scripts/rebuild_runtime_openclaw.sh
 M workspace/scripts/telegram_hardening_helpers.js
 M workspace/scripts/verify_policy_router.sh
 M workspace/state/tacti_cr/events.jsonl
?? docs/GPU_SETUP.md
?? scripts/vllm_prefix_warmup.js
?? tests/safe_error_surface.test.js.bak.20260221T234009Z
?? tests/safe_error_surface.test.js.bak.20260221T234700Z
?? tests/safe_error_surface.test.js.bak.20260221T235149Z
?? tests_unittest/test_discord_thin_adapter.py
?? tests_unittest/test_mcporter_tool_plane.py
?? tests_unittest/test_policy_router_capability_classes.py.bak.20260221T234009Z
?? tests_unittest/test_policy_router_capability_classes.py.bak.20260221T234700Z
?? tests_unittest/test_policy_router_capability_classes.py.bak.20260221T235149Z
?? tests_unittest/test_safe_error_surface.py.bak.20260221T234700Z
?? tests_unittest/test_safe_error_surface.py.bak.20260221T235149Z
?? workspace/NOVELTY_LOVE_ALIGNMENT_RECS.md
?? workspace/NOVELTY_LOVE_ALIGNMENT_TODO.md
?? workspace/artifacts/itc/events/itc_events.jsonl
?? workspace/audit/dali_cbp_discord_vllm_redaction_20260221T232545Z.md
?? workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md.bak.20260221T235149Z
?? workspace/audit/dali_vllm_duplicate_audit_20260221T204359Z.md
?? workspace/docs/ops/DISCORD_THIN_ADAPTER.md
?? workspace/policy/llm_policy.json.bak.20260221T231425Z
?? workspace/scripts/discord_adapter.py
?? workspace/scripts/gateway_router.py
?? workspace/scripts/mcporter_tool_plane.py
?? workspace/scripts/policy_router.py.bak.20260221T231425Z
?? workspace/scripts/policy_router.py.bak.20260221T234009Z
?? workspace/scripts/policy_router.py.bak.20260221T234700Z
?? workspace/scripts/policy_router.py.bak.20260221T235149Z
?? workspace/scripts/rebuild_runtime_openclaw.sh.bak.20260221T231425Z
?? workspace/scripts/safe_error_surface.js.bak.20260221T234009Z
?? workspace/scripts/safe_error_surface.js.bak.20260221T234700Z
?? workspace/scripts/safe_error_surface.js.bak.20260221T235149Z
?? workspace/scripts/safe_error_surface.py.bak.20260221T234009Z
?? workspace/scripts/safe_error_surface.py.bak.20260221T234700Z
?? workspace/scripts/safe_error_surface.py.bak.20260221T235149Z
?? workspace/scripts/telegram_hardening_helpers.js.bak.20260221T231425Z
?? workspace/scripts/verify_policy_router.sh.bak.20260221T231425Z

[git diff --name-status]
M	workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md
M	workspace/policy/llm_policy.json
M	workspace/scripts/rebuild_runtime_openclaw.sh
M	workspace/scripts/telegram_hardening_helpers.js
M	workspace/scripts/verify_policy_router.sh
M	workspace/state/tacti_cr/events.jsonl

note: git fetch origin failed in this environment due DNS/network restriction; local origin/main ref was used for worktree creation.

## Clean Worktree Rebuild + Verification @ aee1ca93516ff7ed887f17dc67ba3f3025771198

isolation_method=git worktree
worktree_path=/tmp/wt_safe_surface
cherry_picks=1bf2517e7d423c6443feba87f4f4ba058b96522f,7480b24da4e0ac8994f28acd47eb4891ccc8e4db

backup_churn_check=find . -name '*.bak.*' -> none

current git status --porcelain -uall:
 M tests/safe_error_surface.test.js
 M workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md
 M workspace/scripts/policy_router.py

current git diff --name-status origin/main...HEAD:
A	tests/safe_error_surface.test.js
A	tests_unittest/test_policy_router_capability_classes.py
A	tests_unittest/test_safe_error_surface.py
A	workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md
M	workspace/scripts/policy_router.py
A	workspace/scripts/safe_error_surface.js
A	workspace/scripts/safe_error_surface.py

verification command outputs:

$ node tests/safe_error_surface.test.js
PASS redact hides bearer/api keys/cookies
PASS safe envelope keeps stable public surface
PASS safe envelope redacts malicious public message text
PASS adapter error text excludes internal log hints

$ python3 -m unittest tests_unittest.test_policy_router_capability_classes -v
test_classifier_mechanical_examples (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_classifier_mechanical_examples) ... ok
test_classifier_negative_guards_prevent_overcapture (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_classifier_negative_guards_prevent_overcapture) ... ok
test_explain_and_apply_patch_routes_to_mechanical_provider (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_explain_and_apply_patch_routes_to_mechanical_provider) ... ok
test_mechanical_execution_prefers_local_vllm (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_mechanical_execution_prefers_local_vllm) ... ok
test_planning_synthesis_prefers_cloud (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_planning_synthesis_prefers_cloud) ... ok
test_router_logs_request_id_latency_outcome (tests_unittest.test_policy_router_capability_classes.TestPolicyRouterCapabilityClasses.test_router_logs_request_id_latency_outcome) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.002s

OK

$ python3 -m unittest tests_unittest.test_safe_error_surface -v
test_envelope_redacts_malicious_public_message (tests_unittest.test_safe_error_surface.TestSafeErrorSurface.test_envelope_redacts_malicious_public_message) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK

$ bash workspace/scripts/verify_policy_router.sh
ok

failure_to_pass_summary=
- initial clean cherry-pick run failed due policy_router merge artifact (syntax) and missing telegram helper import in tests/safe_error_surface.test.js
- then verify_policy_router failed because default capability providers (planningProvider/mechanicalProvider) overshadowed scenario-specific reasoningProvider/codeProvider in merged policies
- resolved by repairing execute_with_escalation initialization/syntax, removing external helper dependency in node test, and applying explicit-provider precedence + small-code selection in capability routing
- final rerun: all four required commands passed

## Clean Worktree Rebuild + Verification @ 1f3cd4fd5edeb3113dd20b7b58ff9b178aa7839a

timestamp_utc=2026-02-22T00:11:19Z
worktree_path=/tmp/wt_safe_surface

git status --porcelain -uall (post-fix):
 M workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md

git diff --name-status origin/main...HEAD (post-fix):
A	tests/safe_error_surface.test.js
A	tests_unittest/test_policy_router_capability_classes.py
A	tests_unittest/test_safe_error_surface.py
A	workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md
M	workspace/scripts/policy_router.py
A	workspace/scripts/safe_error_surface.js
A	workspace/scripts/safe_error_surface.py

final verification summary:
- node tests/safe_error_surface.test.js -> PASS
- python3 -m unittest tests_unittest.test_policy_router_capability_classes -v -> OK
- python3 -m unittest tests_unittest.test_safe_error_surface -v -> OK
- bash workspace/scripts/verify_policy_router.sh -> ok

## Phase X — Re-verify on clean branch @ 1c0a6220a0e743dac0684309dc7c131e82e327f7 (2026-02-22T00:15:32Z)

date_utc=2026-02-22T00:15:32Z
head=1c0a6220a0e743dac0684309dc7c131e82e327f7

git status --porcelain -uall:

git diff --name-status origin/main...HEAD:
A	tests/safe_error_surface.test.js
A	tests_unittest/test_policy_router_capability_classes.py
A	tests_unittest/test_safe_error_surface.py
A	workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md
M	workspace/scripts/policy_router.py
A	workspace/scripts/safe_error_surface.js
A	workspace/scripts/safe_error_surface.py

quiesce notes:
- attempted: systemctl --user stop openclaw-gateway.service
- result: failed to connect to bus (Operation not permitted)
- fallback exact kill command used: kill 39472
- fallback post-check: no exact openclaw-gateway process remained

$ node tests/safe_error_surface.test.js
PASS redact hides bearer/api keys/cookies
PASS safe envelope keeps stable public surface
PASS safe envelope redacts malicious public message text
PASS adapter error text excludes internal log hints

$ python3 -m unittest tests_unittest.test_policy_router_capability_classes -v

$ python3 -m unittest tests_unittest.test_safe_error_surface -v

$ bash workspace/scripts/verify_policy_router.sh
ok
