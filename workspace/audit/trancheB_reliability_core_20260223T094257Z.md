# Tranche B - Reliability Core (20260223T094257Z)

## Phase 0 Baseline
$ git fetch origin
already executed
$ git checkout -b codex/feat/tranche-b-20260223 origin/main
codex/feat/tranche-b-20260223
$ git status --porcelain -uall
?? workspace/audit/trancheB_reliability_core_20260223T094257Z.md
$ node -v
v22.22.0
$ python3 --version
Python 3.12.3

## Phase 0 Recon Findings
$ git rev-parse --abbrev-ref HEAD
codex/feat/tranche-b-20260223
$ git rev-parse HEAD
728877a56c2beb1cce6d1f16c51983088b230a03
$ git status --porcelain -uall
?? workspace/audit/trancheB_reliability_core_20260223T094257Z.md

Pairing/Spawn surfaces located:
- `workspace/scripts/message_handler.py` (`spawn_chatgpt_subagent`)
- `workspace/scripts/check_gateway_pairing_health.sh` (guard)
- `workspace/scripts/pairing_preflight.py` did not exist at baseline

Monitoring surfaces located:
- `workspace/scripts/system_health_monitor.py`
- `scripts/system2/provider_diag.js`
- `scripts/dali_canary_runner.py`

Telegram findings:
- No active Node runtime Telegram webhook handler source in this tree (`core/` has inference modules only).
- Existing repo-visible Telegram path in this branch was script-level tooling; reliability helper added in this tranche under `scripts/system2/telegram_reliability.js`.

## Phase 1 Implementation (Pairing + Spawn)
- Added deterministic preflight module: `workspace/scripts/pairing_preflight.py`
  - lock/dedupe + cooldown + reason enum
  - single-shot remediation for stale pairing
  - structured status: `{ok, reason, remedy, ts, corr_id, observations}`
- Updated `workspace/scripts/message_handler.py`
  - spawn path now always runs preflight
  - structured `PAIRING_UNHEALTHY` error envelope on block
  - event envelope emission: `event=subagent.spawn.blocked`
  - bounded one-shot retry only after safe stale-refresh signal
- Added tests:
  - `tests_unittest/test_pairing_preflight.py`
  - `tests_unittest/test_message_handler_pairing_preflight.py`

## Phase 2 Implementation (Telegram Reliability)
- Added `scripts/system2/telegram_reliability.js`
  - `fastAck()` (immediate ACK contract)
  - `shouldDefer()` for heavy/media payloads
  - `withRetry()` bounded backoff for transient errors
  - `writeDeadletter()` metadata-only JSONL writer (no raw content)
- Added tests:
  - `tests/telegram_fast_ack.test.js`
  - `tests/telegram_defer.test.js`
  - `tests/telegram_deadletter_writer.test.js`

## Phase 3 Implementation (Actionable Health)
- Updated `workspace/scripts/system_health_monitor.py`
  - added `build_actionable_hints()` cause+remedy mapping
  - emits envelope events: `health.ok|health.degraded|health.fail`
- Updated `scripts/system2/provider_diag.js`
  - adds pairing canary probe markers
  - adds deterministic `actionable_next_steps` section
- Updated test:
  - `tests/provider_diag_format.test.js` (new stable markers)
- Added test:
  - `tests_unittest/test_system_health_action_hints.py`

## Verification Commands + Outputs
Initial test run (before minimal fix):
$ python3 -m unittest -v tests_unittest.test_pairing_preflight tests_unittest.test_message_handler_pairing_preflight tests_unittest.test_system_health_action_hints
ERROR: `ModuleNotFoundError: No module named 'aiohttp'` when importing `workspace/scripts/message_handler.py`.
Minimal fix applied: lazy-safe `aiohttp` import with runtime guard in dispatch functions.

Final python tests:
$ python3 -m unittest -v tests_unittest.test_pairing_preflight tests_unittest.test_message_handler_pairing_preflight tests_unittest.test_system_health_action_hints
Ran 8 tests in 0.005s
OK

Final node tests:
$ node tests/provider_diag_format.test.js
PASS provider_diag includes grep-friendly providers_summary section
provider_diag_format tests complete
$ node tests/telegram_fast_ack.test.js
PASS fast ack returns immediate 200 with deferred=false for small payload
telegram_fast_ack tests complete
$ node tests/telegram_defer.test.js
PASS large payloads are deferred
PASS media payloads are deferred
PASS retry helper retries transient failure once
telegram_defer tests complete
$ node tests/telegram_deadletter_writer.test.js
PASS deadletter writer stores metadata only and stable envelope fields
telegram_deadletter_writer tests complete

Additional regression check:
$ node tests/provider_diag_never_unknown.test.js
PASS journal unavailable maps to UNAVAILABLE and never UNKNOWN
PASS journal marker maps to DEGRADED reason from marker
PASS journal with no marker maps to NO_BLOCK_MARKER and DOWN
provider_diag_never_unknown tests complete

Smoke output excerpts:
$ node scripts/system2/provider_diag.js
- `coder_status=UP`
- `pairing_canary_status=OK`
- `actionable_next_steps:` then `- none`

$ python3 workspace/scripts/system_health_monitor.py
- `overall_pass=false` (assistant vLLM endpoint :8001 refused)
- actionable hint emitted:
  - component=`vllm`
  - remedy=`systemctl --user status openclaw-vllm.service` + curl health check

## Rollback
- Pairing/spawn commit: `git revert <sha>`
- Telegram reliability commit: `git revert <sha>`
- Health/diag commit: `git revert <sha>`
- Runtime log artifacts are outside repo and can be left in place.

## Residual Uncertainties
- Telegram runtime webhook integration point is not present in this repository tree; helper module is ready for wiring by runtime entrypoint owners.
- Health smoke observed local assistant vLLM endpoint (:8001) down in this host state; coder lane (:8002) was up.

## Final Post-Commit Verification
$ git --no-pager log --oneline -n 4
2a90924 feat(health): actionable reason+remedy output; emit event envelopes
abf97ad feat(telegram): fast-ack + defer heavy updates; tighten retries and deadletter
2043550 feat(pairing): tighten spawn preflight, structured errors, and self-heal classification
728877a merge: tranche A security + ops hygiene

$ node scripts/system2/provider_diag.js
Key markers:
- coder_status=UP
- coder_degraded_reason=OK
- replay_log_writable=true
- pairing_canary_status=OK
- actionable_next_steps: none

$ python3 workspace/scripts/system_health_monitor.py
Key markers:
- overall_pass=false
- failing component: vllm (127.0.0.1:8001 refused)
- actionable_hints includes explicit remedy (`systemctl --user status openclaw-vllm.service`, curl health check)
- event_envelope.event=health.fail
