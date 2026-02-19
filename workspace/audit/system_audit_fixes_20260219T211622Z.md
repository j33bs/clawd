# System audit fixes

- UTC: 20260219T211622Z
- Branch: codex/fix/audit-policy-router-tests-20260220

## Phase 0 Baseline

```text
$ git status --porcelain -uall
 M .claude/worktrees/crazy-brahmagupta
 M .claude/worktrees/elastic-swirles
 M memory/literature/state.json
 M workspace/state/tacti_cr/events.jsonl
?? workspace/CODEX_Source_UI_TACTI_Upgrade.md
?? workspace/skill-graph/mocs/consciousness-research.md
?? workspace/skill-graph/skills/active-inference.md
?? workspace/skill-graph/skills/embodied-cognition.md
?? workspace/skill-graph/skills/global-neuronal-workspace.md
?? workspace/skill-graph/skills/hierarchical-temporal-memory.md
?? workspace/skill-graph/skills/integrated-information-theory.md
?? workspace/skill-graph/skills/physical-ai.md
?? workspace/skill-graph/skills/swarm-intelligence.md

$ git rev-parse --short HEAD
32a2cd5

$ git branch --show-current
feature/source-ui-tacti-cr-20260219

$ node -v
v25.6.0

$ npm -v
11.8.0

$ python3 -V
Python 3.14.3
```

## Phase 1 Reproduction

### python_unittest_q

```text
$ python3 -m unittest -q || true
(exit=0)
2:ERROR: tests_unittest.test_itc_pipeline (unittest.loader._FailedTest)
4:ImportError: Failed to import test module: tests_unittest.test_itc_pipeline
5:Traceback (most recent call last):
8:ModuleNotFoundError: No module named 'yaml'
12:Traceback (most recent call last):
25:ERROR: test_invalid_policy_typo_fails_closed_by_default (tests_unittest.test_llm_policy_schema_validation.TestLlmPolicySchemaValidation)
27:Traceback (most recent call last):
29:    with self.assertRaises(policy_router.PolicyValidationError) as ctx:
30:AttributeError: module 'policy_router' has no attribute 'PolicyValidationError'
33:ERROR: test_provider_unknown_key_fails_closed_by_default (tests_unittest.test_llm_policy_schema_validation.TestLlmPolicySchemaValidation)
35:Traceback (most recent call last):
37:    with self.assertRaises(policy_router.PolicyValidationError) as ctx:
38:AttributeError: module 'policy_router' has no attribute 'PolicyValidationError'
41:ERROR: test_active_inference_predict_and_update_in_execute (tests_unittest.test_policy_router_active_inference_hook.TestPolicyRouterActiveInferenceHook)
43:Traceback (most recent call last):
49:    raise AttributeError(
50:AttributeError: <module 'policy_router' from '/Users/heathyeager/clawd/workspace/scripts/policy_router.py'> does not have the attribute 'ACTIVE_INFERENCE_STATE_PATH'
53:ERROR: test_flags_off_preserves_flow_without_tacti_hook_invocation (tests_unittest.test_policy_router_tacti_main_flow.TestPolicyRouterTactiMainFlow)
55:Traceback (most recent call last):
61:    raise AttributeError(
62:AttributeError: <module 'policy_router' from '/Users/heathyeager/clawd/workspace/scripts/policy_router.py'> does not have the attribute 'tacti_enhance_plan'
65:FAIL: test_verifier_passes_in_repo (tests_unittest.test_goal_identity_invariants.TestGoalIdentityInvariants)
67:Traceback (most recent call last):
70:AssertionError: 2 != 0 : FAIL: policy routing.free_order must be ['google-gemini-cli', 'qwen-portal', 'groq', 'ollama'] (got ['local_vllm_assistant', 'ollama', 'groq', 'qwen'])
75:FAIL: test_flag_on_runs_tacti_hook_and_records_non_empty_agent_ids (tests_unittest.test_policy_router_tacti_main_flow.TestPolicyRouterTactiMainFlow)
77:Traceback (most recent call last):
80:AssertionError: False is not true
85:FAILED (failures=2, errors=5)
86:ERROR: pyyaml not installed. Run: pip install pyyaml
```

### verify_team_chat

```text
$ bash workspace/scripts/verify_team_chat.sh || true
(exit=0)
{"session_id": "verify_teamchat_offline", "status": "accepted", "cycles": 1, "paths": {"session_jsonl": "/tmp/teamchat_verify/sessions/verify_teamchat_offline.jsonl", "summary_md": "/tmp/teamchat_verify/summaries/verify_teamchat_offline.md", "state_json": "/tmp/teamchat_verify/state/verify_teamchat_offline.json"}}
ok
```

### verify_goal_identity_invariants

```text
$ python3 workspace/scripts/verify_goal_identity_invariants.py || true
(exit=0)
1:FAIL: policy routing.free_order must be ['google-gemini-cli', 'qwen-portal', 'groq', 'ollama'] (got ['local_vllm_assistant', 'ollama', 'groq', 'qwen'])
```

### npm_test_silent

```text
$ npm test --silent || true
(exit=0)
4:ERROR: test_itc_pipeline (unittest.loader._FailedTest)
6:ImportError: Failed to import test module: test_itc_pipeline
7:Traceback (most recent call last):
10:ModuleNotFoundError: No module named 'yaml'
14:Traceback (most recent call last):
27:ERROR: test_invalid_policy_typo_fails_closed_by_default (test_llm_policy_schema_validation.TestLlmPolicySchemaValidation)
29:Traceback (most recent call last):
31:    with self.assertRaises(policy_router.PolicyValidationError) as ctx:
32:AttributeError: module 'policy_router' has no attribute 'PolicyValidationError'
35:ERROR: test_provider_unknown_key_fails_closed_by_default (test_llm_policy_schema_validation.TestLlmPolicySchemaValidation)
37:Traceback (most recent call last):
39:    with self.assertRaises(policy_router.PolicyValidationError) as ctx:
40:AttributeError: module 'policy_router' has no attribute 'PolicyValidationError'
43:ERROR: test_active_inference_predict_and_update_in_execute (test_policy_router_active_inference_hook.TestPolicyRouterActiveInferenceHook)
45:Traceback (most recent call last):
51:    raise AttributeError(
52:AttributeError: <module 'policy_router' from '/Users/heathyeager/clawd/workspace/scripts/policy_router.py'> does not have the attribute 'ACTIVE_INFERENCE_STATE_PATH'
55:ERROR: test_flags_off_preserves_flow_without_tacti_hook_invocation (test_policy_router_tacti_main_flow.TestPolicyRouterTactiMainFlow)
57:Traceback (most recent call last):
63:    raise AttributeError(
64:AttributeError: <module 'policy_router' from '/Users/heathyeager/clawd/workspace/scripts/policy_router.py'> does not have the attribute 'tacti_enhance_plan'
67:FAIL: test_verifier_passes_in_repo (test_goal_identity_invariants.TestGoalIdentityInvariants)
69:Traceback (most recent call last):
72:AssertionError: 2 != 0 : FAIL: policy routing.free_order must be ['google-gemini-cli', 'qwen-portal', 'groq', 'ollama'] (got ['local_vllm_assistant', 'ollama', 'groq', 'qwen'])
77:FAIL: test_flag_on_runs_tacti_hook_and_records_non_empty_agent_ids (test_policy_router_tacti_main_flow.TestPolicyRouterTactiMainFlow)
79:Traceback (most recent call last):
82:AssertionError: False is not true
87:FAILED (failures=2, errors=5)
88:ERROR: pyyaml not installed. Run: pip install pyyaml
138:PASS ask_first surfaces deny decisions as ToolDeniedError
173:PASS classifyDispatchError: timeout
174:PASS classifyDispatchError: auth/config/http
187:  throw new AssertionError(obj);
190:AssertionError [ERR_ASSERTION]: policy.providers.openai_auth.enabled must be false
334:FAILURES: 2/38
```

### jest_freecompute_cloud

```text
$ npx jest tests/freecompute_cloud.test.js -i --runInBand || true
(exit=0)
1:npm WARN exec The following package was not found and will be installed: jest@30.2.0
11:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
26:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
41:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
57:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
72:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
```

### jest_model_routing_no_oauth

```text
$ npx jest tests/model_routing_no_oauth.test.js -i --runInBand || true
(exit=0)
1:FAIL .claude/worktrees/trusting-lamarr/tests/model_routing_no_oauth.test.js
4:    AssertionError [ERR_ASSERTION]: policy.providers.openai_auth.enabled must be false
17:FAIL .claude/worktrees/strange-vaughan/tests/model_routing_no_oauth.test.js
28:FAIL .claude/worktrees/cranky-cartwright/tests/model_routing_no_oauth.test.js
39:FAIL .claude/worktrees/elastic-swirles/tests/model_routing_no_oauth.test.js
50:FAIL .claude/worktrees/adoring-bose/tests/model_routing_no_oauth.test.js
61:FAIL .claude/worktrees/crazy-brahmagupta/tests/model_routing_no_oauth.test.js
72:FAIL .claude/worktrees/condescending-varahamihira/tests/model_routing_no_oauth.test.js
83:FAIL tests/model_routing_no_oauth.test.js
86:    AssertionError [ERR_ASSERTION]: policy.providers.openai_auth.enabled must be false
```

## Phase 2 Verification

### py_compile_policy_router

```text
$ python3 -m py_compile workspace/scripts/policy_router.py
(exit=0)
```

### unittest_policy_schema

```text
$ python3 -m unittest -q tests_unittest.test_llm_policy_schema_validation
(exit=0)
----------------------------------------------------------------------
Ran 4 tests in 0.046s

OK
```

### unittest_policy_router_active_inference

```text
$ python3 -m unittest -q tests_unittest.test_policy_router_active_inference_hook
(exit=1)
2:FAIL: test_active_inference_predict_and_update_in_execute (tests_unittest.test_policy_router_active_inference_hook.TestPolicyRouterActiveInferenceHook)
4:Traceback (most recent call last):
7:AssertionError: False is not true
12:FAILED (failures=1)
```

### unittest_policy_router_tacti_main_flow

```text
$ python3 -m unittest -q tests_unittest.test_policy_router_tacti_main_flow
(exit=1)
2:FAIL: test_flag_on_runs_tacti_hook_and_records_non_empty_agent_ids (tests_unittest.test_policy_router_tacti_main_flow.TestPolicyRouterTactiMainFlow)
4:Traceback (most recent call last):
7:AssertionError: False is not true
10:FAIL: test_flags_off_preserves_flow_without_tacti_hook_invocation (tests_unittest.test_policy_router_tacti_main_flow.TestPolicyRouterTactiMainFlow)
12:Traceback (most recent call last):
15:AssertionError: False is not true
20:FAILED (failures=2)
```

### python_unittest_q_after_phase2

```text
$ python3 -m unittest -q
(exit=1)
2:ERROR: tests_unittest.test_itc_pipeline (unittest.loader._FailedTest)
5:Traceback (most recent call last):
12:Traceback (most recent call last):
25:FAIL: test_verifier_passes_in_repo (tests_unittest.test_goal_identity_invariants.TestGoalIdentityInvariants)
27:Traceback (most recent call last):
30:AssertionError: 2 != 0 : FAIL: policy routing.free_order must be ['google-gemini-cli', 'qwen-portal', 'groq', 'ollama'] (got ['local_vllm_assistant', 'ollama', 'groq', 'qwen'])
35:FAIL: test_active_inference_predict_and_update_in_execute (tests_unittest.test_policy_router_active_inference_hook.TestPolicyRouterActiveInferenceHook)
37:Traceback (most recent call last):
40:AssertionError: False is not true
43:FAIL: test_flag_on_runs_tacti_hook_and_records_non_empty_agent_ids (tests_unittest.test_policy_router_tacti_main_flow.TestPolicyRouterTactiMainFlow)
45:Traceback (most recent call last):
48:AssertionError: False is not true
51:FAIL: test_flags_off_preserves_flow_without_tacti_hook_invocation (tests_unittest.test_policy_router_tacti_main_flow.TestPolicyRouterTactiMainFlow)
53:Traceback (most recent call last):
56:AssertionError: False is not true
61:FAILED (failures=4, errors=1)
62:ERROR: pyyaml not installed. Run: pip install pyyaml
```

## Phase 3 Verification

### verify_goal_identity_invariants_phase3

```text
$ python3 workspace/scripts/verify_goal_identity_invariants.py
(exit=0)
```

### rg_goal_identity_fail_pattern

```text
$ rg -n 'FAIL:|repo-root governance file present' -S workspace/scripts/verify_goal_identity_invariants.py
(exit=0)
1:38:    print(f"FAIL: {msg}")
```

### unittest_policy_router_active_inference_phase3

```text
$ python3 -m unittest -q tests_unittest.test_policy_router_active_inference_hook
(exit=0)
----------------------------------------------------------------------
Ran 1 test in 0.003s

OK
```

### unittest_policy_router_tacti_main_flow_phase3

```text
$ python3 -m unittest -q tests_unittest.test_policy_router_tacti_main_flow
(exit=0)
----------------------------------------------------------------------
Ran 2 tests in 0.006s

OK
```

### python_unittest_q_phase3

```text
$ python3 -m unittest -q
(exit=1)
2:ERROR: tests_unittest.test_itc_pipeline (unittest.loader._FailedTest)
5:Traceback (most recent call last):
12:Traceback (most recent call last):
27:FAILED (errors=1)
28:ERROR: pyyaml not installed. Run: pip install pyyaml
```

## Phase 4 jest_freecompute_cloud_detect

```text
$ npx jest tests/freecompute_cloud.test.js -i --runInBand --detectOpenHandles
(exit=0)
2:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
17:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
32:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
48:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
63:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
```

## Phase 4 jest_model_routing_no_oauth_detect

```text
$ npx jest tests/model_routing_no_oauth.test.js -i --runInBand --detectOpenHandles
(exit=1)
1:FAIL .claude/worktrees/strange-vaughan/tests/model_routing_no_oauth.test.js
12:FAIL .claude/worktrees/elastic-swirles/tests/model_routing_no_oauth.test.js
23:FAIL .claude/worktrees/crazy-brahmagupta/tests/model_routing_no_oauth.test.js
34:FAIL .claude/worktrees/trusting-lamarr/tests/model_routing_no_oauth.test.js
37:    AssertionError [ERR_ASSERTION]: policy.providers.openai_auth.enabled must be false
50:FAIL .claude/worktrees/cranky-cartwright/tests/model_routing_no_oauth.test.js
61:FAIL .claude/worktrees/condescending-varahamihira/tests/model_routing_no_oauth.test.js
72:FAIL .claude/worktrees/adoring-bose/tests/model_routing_no_oauth.test.js
83:FAIL tests/model_routing_no_oauth.test.js
```

## Phase 4 npm_test_silent_phase4

```text
$ npm test --silent
(exit=1)
4:ERROR: test_itc_pipeline (unittest.loader._FailedTest)
29:FAILED (errors=1)
30:ERROR: pyyaml not installed. Run: pip install pyyaml
73:PASS analyze_session_patterns aggregates recurring inefficiency patterns
75:PASS anticipate module emits suggestion-only low-risk automation hints
76:PASS anticipate feature flag disables suggestions
78:PASS ask_first enforces approval for exec
79:PASS ask_first allows ask-decision action with operator approval
80:PASS ask_first surfaces deny decisions as ToolDeniedError
82:PASS audit sink hash chaining persists across rotation
84:PASS starts in closed state with zero usage
85:PASS records usage and decrements remaining
86:PASS trips on token cap exceeded
87:PASS trips on call cap exceeded
88:PASS rejects usage when open
89:PASS canProceed returns false when open
90:PASS canProceed returns false when estimate exceeds remaining
91:PASS reset restores closed state
92:PASS reset with new caps
95:PASS context sanitizer redacts tool-shaped JSON payload
96:PASS context sanitizer strips role/authority prefixes
97:PASS context sanitizer preserves normal human text
115:PASS classifyDispatchError: timeout
116:PASS classifyDispatchError: auth/config/http
118:PASS integrity baseline is deterministic
119:PASS integrity drift fails closed and explicit approval recovers
120:PASS runtime identity override metadata is denied
121:PASS integrity guard hook enforces baseline presence
123:PASS parseAddedLegacyMentions finds newly added System-1 references
124:PASS lintLegacyNames ignores files with legacy header notice
126:PASS memory writer sanitizes and appends workspace memory entries
128:PASS model routing no oauth/codex regression gate
130:PASS returns zero findings when relative require resolves
131:PASS reports finding when relative require target is missing
134:PASS moltbook activity aggregates monthly impact from local stub events
136:PASS loads system map with expected defaults
137:PASS normalizes system1/system-1 aliases to dali
138:PASS normalizes system2/system-2 aliases to c_lawd
139:PASS resolves workspace and memory roots from alias
141:PASS provider_diag includes grep-friendly providers_summary section
144:PASS healthProbe succeeds against mocked vLLM endpoint and normalizes /v1
145:PASS healthProbe returns fail-closed result when endpoint is unreachable
146:PASS generateChat returns expected output shape from vLLM response
147:PASS normalizeBaseUrl appends /v1 only when missing
149:PASS idempotent: applying rules twice yields same result
150:PASS JSON validity preserved after redaction
151:PASS no /Users/ or heathyeager remains after redaction
152:PASS repo root path replaced correctly
153:PASS openclaw config path replaced correctly
154:PASS generic home path replaced correctly
155:PASS ls -la line replaced correctly
156:PASS standalone username replaced
157:PASS timestamps, hashes, exit codes not redacted
158:PASS placeholders are not themselves redactable patterns
159:PASS CLI redacts synthetic fixtures and writes output bundle
160:PASS CLI dry-run emits summary and does not write output files
162:PASS provider mapping exposes required env vars
163:PASS maskSecretFingerprint never returns raw secret value
164:PASS bridge serialization does not expose env secret values
165:PASS injectRuntimeEnv respects operator override and injects missing
166:PASS injectRuntimeEnv propagates GROQ_API_KEY operator override to OPENCLAW_GROQ_API_KEY
167:PASS config includes secrets bridge governance knobs
168:PASS redaction covers mapped secret env vars
169:PASS auto backend detection is platform deterministic
170:PASS file backend requires explicit opt-in
172:PASS secrets cli exec injects alias env keys without printing values
174:PASS plugin registers CLI command: secrets
175:PASS secrets cli status prints enablement header (no secrets)
178:PASS skill composer is disabled by default
179:PASS skill composer respects tool governance decisions
181:PASS createVllmProvider ignores SYSTEM2_VLLM_* when system2 is false
182:PASS probeVllmServer ignores SYSTEM2_VLLM_* when system2 is false
183:PASS probeVllmServer consults SYSTEM2_VLLM_* when system2 is true
184:PASS probeVllmServer consults SYSTEM2_VLLM_* when nodeId alias resolves to c_lawd
186:PASS resolves with explicit args (highest precedence)
187:PASS falls back to SYSTEM2_VLLM_* env vars
188:PASS falls back to OPENCLAW_VLLM_* env vars
189:PASS prefers SYSTEM2_VLLM_* over OPENCLAW_VLLM_*
190:PASS uses node alias system-2 for c_lawd routing context
191:PASS uses defaults when envs not set
192:PASS emits diagnostic events (keys only)
193:PASS resolves numeric config deterministically
194:PASS invalid numeric env yields NaN (no throw)
196:PASS buildEvidenceBundle captures raw, writes redacted output, and emits manifest
197:PASS buildEvidenceBundle preserves fail-closed snapshot status
199:PASS no-change fixture yields INCONCLUSIVE
200:PASS improvement fixture yields KEEP
201:PASS regression fixture yields REVERT
202:PASS auth preset script maps to calibrated fail-on path
203:PASS calibrated auth fail-on yields REVERT on regression fixture
204:PASS failing subprocess writes UNAVAILABLE report and exits 3
206:PASS FederatedEnvelopeV1 fixture validates (strict)
207:PASS FederatedEnvelopeV1 rejects invalid schema (fail-closed)
208:PASS System2EventV1 fixture validates
209:PASS JSONL sink contract is deterministic (exact line match)
210:PASS redaction-at-write is deterministic and idempotent
211:PASS gating: disabled emitter is a no-op
212:PASS gating: enabled emitter appends a redacted event
213:PASS emitter does not throw on sink error by default (strict=false)
214:PASS emitter fails closed on sink error when strict=true
216:PASS edge rejects missing/invalid auth and does not log secrets
217:PASS edge rate limits per identity
218:PASS edge enforces body size limit (413)
219:PASS rpc routes require approval (fail-closed)
220:PASS malformed read tool payloads are denied at edge
221:PASS websocket upgrade requires approval (fail-closed)
222:PASS non-loopback bind requires explicit opt-in
223:PASS HMAC signing auth (replay resistant)
224:PASS HMAC mode can allow loopback Bearer (opt-in)
225:PASS audit sink writes JSONL and rotates (no secrets)
226:PASS tokens/hmac keys file mode is enforced (0600)
227:PASS inflight caps + timeouts are enforced/configured
230:PASS system2 repair auth-profiles acceptance check
232:PASS system2 repair models acceptance check
234:PASS system2 repair scripts regression gate
236:PASS captureSnapshot writes stable files and summary shape
237:PASS captureSnapshot fail-closed with partial outputs when command fails
239:PASS JSON output is stable and ignores timestamp fields by default
240:PASS ignore list suppresses expected diff paths and exits 0
241:PASS fail-on marks regressions and exits 2
242:PASS human output includes summary counts and regression marker
243:PASS computeDiff supports deterministic dotpath flattening
245:PASS OFF: system2.observability.enabled=false emits nothing and writes no JSONL
246:PASS ON: system2.observability.enabled=true writes exactly one deterministic JSONL line
248:PASS tacticr feedback writer appends schema-valid sanitized JSONL entries
249:PASS tacticr feedback writer enforces required schema fields
251:PASS tool governance allows explicit allowlist actions
252:PASS tool governance asks for exec/network/outside-workspace writes
253:PASS tool governance denies explicit denylist actions
255:PASS http edge governance hook maps approval/deny errors deterministically
256:FAILURES: 1/38
```

### jest_freecompute_cloud_detect_after_fix

```text
$ npx jest tests/freecompute_cloud.test.js -i --runInBand --detectOpenHandles
(exit=0)
38:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
53:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
68:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
76:      1241 | console.log(`FreeComputeCloud Tests: ${passed} passed, ${failed} failed, ${skipped} skipped`);
84:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
85:    Attempted to log "FreeComputeCloud Tests: 70 passed, 0 failed, 3 skipped".
89:    > 1241 | console.log(`FreeComputeCloud Tests: ${passed} passed, ${failed} failed, ${skipped} skipped`);
99:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
```

### jest_model_routing_no_oauth_detect_after_fix

```text
$ npx jest tests/model_routing_no_oauth.test.js -i --runInBand --detectOpenHandles
(exit=1)
2:    PASS model routing no oauth/codex regression gate
6:FAIL tests/model_routing_no_oauth.test.js
17:Test Suites: 1 failed, 1 total
18:Tests:       0 total
```

### npm_test_silent_after_js_fix

```text
$ npm test --silent
(exit=1)
4:ERROR: test_itc_pipeline (unittest.loader._FailedTest)
29:FAILED (errors=1)
30:ERROR: pyyaml not installed. Run: pip install pyyaml
73:PASS analyze_session_patterns aggregates recurring inefficiency patterns
75:PASS anticipate module emits suggestion-only low-risk automation hints
76:PASS anticipate feature flag disables suggestions
78:PASS ask_first enforces approval for exec
79:PASS ask_first allows ask-decision action with operator approval
80:PASS ask_first surfaces deny decisions as ToolDeniedError
82:PASS audit sink hash chaining persists across rotation
84:PASS starts in closed state with zero usage
85:PASS records usage and decrements remaining
86:PASS trips on token cap exceeded
87:PASS trips on call cap exceeded
88:PASS rejects usage when open
89:PASS canProceed returns false when open
90:PASS canProceed returns false when estimate exceeds remaining
91:PASS reset restores closed state
92:PASS reset with new caps
95:PASS context sanitizer redacts tool-shaped JSON payload
96:PASS context sanitizer strips role/authority prefixes
97:PASS context sanitizer preserves normal human text
111:FreeComputeCloud Tests: 70 passed, 0 failed, 3 skipped
115:PASS classifyDispatchError: timeout
116:PASS classifyDispatchError: auth/config/http
118:PASS integrity baseline is deterministic
119:PASS integrity drift fails closed and explicit approval recovers
120:PASS runtime identity override metadata is denied
121:PASS integrity guard hook enforces baseline presence
123:PASS parseAddedLegacyMentions finds newly added System-1 references
124:PASS lintLegacyNames ignores files with legacy header notice
126:PASS memory writer sanitizes and appends workspace memory entries
128:PASS model routing no oauth/codex regression gate
130:PASS returns zero findings when relative require resolves
131:PASS reports finding when relative require target is missing
134:PASS moltbook activity aggregates monthly impact from local stub events
136:PASS loads system map with expected defaults
137:PASS normalizes system1/system-1 aliases to dali
138:PASS normalizes system2/system-2 aliases to c_lawd
139:PASS resolves workspace and memory roots from alias
141:PASS provider_diag includes grep-friendly providers_summary section
144:PASS healthProbe succeeds against mocked vLLM endpoint and normalizes /v1
145:PASS healthProbe returns fail-closed result when endpoint is unreachable
146:PASS generateChat returns expected output shape from vLLM response
147:PASS normalizeBaseUrl appends /v1 only when missing
149:PASS idempotent: applying rules twice yields same result
150:PASS JSON validity preserved after redaction
151:PASS no /Users/ or heathyeager remains after redaction
152:PASS repo root path replaced correctly
153:PASS openclaw config path replaced correctly
154:PASS generic home path replaced correctly
155:PASS ls -la line replaced correctly
156:PASS standalone username replaced
157:PASS timestamps, hashes, exit codes not redacted
158:PASS placeholders are not themselves redactable patterns
159:PASS CLI redacts synthetic fixtures and writes output bundle
160:PASS CLI dry-run emits summary and does not write output files
162:PASS provider mapping exposes required env vars
163:PASS maskSecretFingerprint never returns raw secret value
164:PASS bridge serialization does not expose env secret values
165:PASS injectRuntimeEnv respects operator override and injects missing
166:PASS injectRuntimeEnv propagates GROQ_API_KEY operator override to OPENCLAW_GROQ_API_KEY
167:PASS config includes secrets bridge governance knobs
168:PASS redaction covers mapped secret env vars
169:PASS auto backend detection is platform deterministic
170:PASS file backend requires explicit opt-in
172:PASS secrets cli exec injects alias env keys without printing values
174:PASS plugin registers CLI command: secrets
175:PASS secrets cli status prints enablement header (no secrets)
178:PASS skill composer is disabled by default
179:PASS skill composer respects tool governance decisions
181:PASS createVllmProvider ignores SYSTEM2_VLLM_* when system2 is false
182:PASS probeVllmServer ignores SYSTEM2_VLLM_* when system2 is false
183:PASS probeVllmServer consults SYSTEM2_VLLM_* when system2 is true
184:PASS probeVllmServer consults SYSTEM2_VLLM_* when nodeId alias resolves to c_lawd
186:PASS resolves with explicit args (highest precedence)
187:PASS falls back to SYSTEM2_VLLM_* env vars
188:PASS falls back to OPENCLAW_VLLM_* env vars
189:PASS prefers SYSTEM2_VLLM_* over OPENCLAW_VLLM_*
190:PASS uses node alias system-2 for c_lawd routing context
191:PASS uses defaults when envs not set
192:PASS emits diagnostic events (keys only)
193:PASS resolves numeric config deterministically
194:PASS invalid numeric env yields NaN (no throw)
196:PASS buildEvidenceBundle captures raw, writes redacted output, and emits manifest
197:PASS buildEvidenceBundle preserves fail-closed snapshot status
199:PASS no-change fixture yields INCONCLUSIVE
200:PASS improvement fixture yields KEEP
201:PASS regression fixture yields REVERT
202:PASS auth preset script maps to calibrated fail-on path
203:PASS calibrated auth fail-on yields REVERT on regression fixture
204:PASS failing subprocess writes UNAVAILABLE report and exits 3
206:PASS FederatedEnvelopeV1 fixture validates (strict)
207:PASS FederatedEnvelopeV1 rejects invalid schema (fail-closed)
208:PASS System2EventV1 fixture validates
209:PASS JSONL sink contract is deterministic (exact line match)
210:PASS redaction-at-write is deterministic and idempotent
211:PASS gating: disabled emitter is a no-op
212:PASS gating: enabled emitter appends a redacted event
213:PASS emitter does not throw on sink error by default (strict=false)
214:PASS emitter fails closed on sink error when strict=true
216:PASS edge rejects missing/invalid auth and does not log secrets
217:PASS edge rate limits per identity
218:PASS edge enforces body size limit (413)
219:PASS rpc routes require approval (fail-closed)
220:PASS malformed read tool payloads are denied at edge
221:PASS websocket upgrade requires approval (fail-closed)
222:PASS non-loopback bind requires explicit opt-in
223:PASS HMAC signing auth (replay resistant)
224:PASS HMAC mode can allow loopback Bearer (opt-in)
225:PASS audit sink writes JSONL and rotates (no secrets)
226:PASS tokens/hmac keys file mode is enforced (0600)
227:PASS inflight caps + timeouts are enforced/configured
230:PASS system2 repair auth-profiles acceptance check
232:PASS system2 repair models acceptance check
234:PASS system2 repair scripts regression gate
236:PASS captureSnapshot writes stable files and summary shape
237:PASS captureSnapshot fail-closed with partial outputs when command fails
239:PASS JSON output is stable and ignores timestamp fields by default
240:PASS ignore list suppresses expected diff paths and exits 0
241:PASS fail-on marks regressions and exits 2
242:PASS human output includes summary counts and regression marker
243:PASS computeDiff supports deterministic dotpath flattening
245:PASS OFF: system2.observability.enabled=false emits nothing and writes no JSONL
246:PASS ON: system2.observability.enabled=true writes exactly one deterministic JSONL line
248:PASS tacticr feedback writer appends schema-valid sanitized JSONL entries
249:PASS tacticr feedback writer enforces required schema fields
251:PASS tool governance allows explicit allowlist actions
252:PASS tool governance asks for exec/network/outside-workspace writes
253:PASS tool governance denies explicit denylist actions
255:PASS http edge governance hook maps approval/deny errors deterministically
256:FAILURES: 1/38
```

### jest_model_routing_no_oauth_detect_after_wrapper

```text
$ npx jest tests/model_routing_no_oauth.test.js -i --runInBand --detectOpenHandles
(exit=0)
2:    PASS model routing no oauth/codex regression gate
6:PASS tests/model_routing_no_oauth.test.js
9:Test Suites: 1 passed, 1 total
10:Tests:       1 passed, 1 total
```

### jest_freecompute_cloud_detect_after_wrapper

```text
$ npx jest tests/freecompute_cloud.test.js -i --runInBand --detectOpenHandles
(exit=0)
38:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
53:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
68:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
76:      1241 | console.log(`FreeComputeCloud Tests: ${passed} passed, ${failed} failed, ${skipped} skipped`);
84:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
85:    Attempted to log "FreeComputeCloud Tests: 70 passed, 0 failed, 3 skipped".
89:    > 1241 | console.log(`FreeComputeCloud Tests: ${passed} passed, ${failed} failed, ${skipped} skipped`);
99:  ●  Cannot log after tests are done. Did you forget to wait for something async in your test?
```

### npm_test_silent_phase4_post_wrapper

```text
$ npm test --silent
(exit=1)
4:ERROR: test_itc_pipeline (unittest.loader._FailedTest)
29:FAILED (errors=1)
30:ERROR: pyyaml not installed. Run: pip install pyyaml
73:PASS analyze_session_patterns aggregates recurring inefficiency patterns
75:PASS anticipate module emits suggestion-only low-risk automation hints
76:PASS anticipate feature flag disables suggestions
78:PASS ask_first enforces approval for exec
79:PASS ask_first allows ask-decision action with operator approval
80:PASS ask_first surfaces deny decisions as ToolDeniedError
82:PASS audit sink hash chaining persists across rotation
84:PASS starts in closed state with zero usage
85:PASS records usage and decrements remaining
86:PASS trips on token cap exceeded
87:PASS trips on call cap exceeded
88:PASS rejects usage when open
89:PASS canProceed returns false when open
90:PASS canProceed returns false when estimate exceeds remaining
91:PASS reset restores closed state
92:PASS reset with new caps
95:PASS context sanitizer redacts tool-shaped JSON payload
96:PASS context sanitizer strips role/authority prefixes
97:PASS context sanitizer preserves normal human text
111:FreeComputeCloud Tests: 70 passed, 0 failed, 3 skipped
115:PASS classifyDispatchError: timeout
116:PASS classifyDispatchError: auth/config/http
118:PASS integrity baseline is deterministic
119:PASS integrity drift fails closed and explicit approval recovers
120:PASS runtime identity override metadata is denied
121:PASS integrity guard hook enforces baseline presence
123:PASS parseAddedLegacyMentions finds newly added System-1 references
124:PASS lintLegacyNames ignores files with legacy header notice
126:PASS memory writer sanitizes and appends workspace memory entries
128:PASS model routing no oauth/codex regression gate
130:PASS returns zero findings when relative require resolves
131:PASS reports finding when relative require target is missing
134:PASS moltbook activity aggregates monthly impact from local stub events
136:PASS loads system map with expected defaults
137:PASS normalizes system1/system-1 aliases to dali
138:PASS normalizes system2/system-2 aliases to c_lawd
139:PASS resolves workspace and memory roots from alias
141:PASS provider_diag includes grep-friendly providers_summary section
144:PASS healthProbe succeeds against mocked vLLM endpoint and normalizes /v1
145:PASS healthProbe returns fail-closed result when endpoint is unreachable
146:PASS generateChat returns expected output shape from vLLM response
147:PASS normalizeBaseUrl appends /v1 only when missing
149:PASS idempotent: applying rules twice yields same result
150:PASS JSON validity preserved after redaction
151:PASS no /Users/ or heathyeager remains after redaction
152:PASS repo root path replaced correctly
153:PASS openclaw config path replaced correctly
154:PASS generic home path replaced correctly
155:PASS ls -la line replaced correctly
156:PASS standalone username replaced
157:PASS timestamps, hashes, exit codes not redacted
158:PASS placeholders are not themselves redactable patterns
159:PASS CLI redacts synthetic fixtures and writes output bundle
160:PASS CLI dry-run emits summary and does not write output files
162:PASS provider mapping exposes required env vars
163:PASS maskSecretFingerprint never returns raw secret value
164:PASS bridge serialization does not expose env secret values
165:PASS injectRuntimeEnv respects operator override and injects missing
166:PASS injectRuntimeEnv propagates GROQ_API_KEY operator override to OPENCLAW_GROQ_API_KEY
167:PASS config includes secrets bridge governance knobs
168:PASS redaction covers mapped secret env vars
169:PASS auto backend detection is platform deterministic
170:PASS file backend requires explicit opt-in
172:PASS secrets cli exec injects alias env keys without printing values
174:PASS plugin registers CLI command: secrets
175:PASS secrets cli status prints enablement header (no secrets)
178:PASS skill composer is disabled by default
179:PASS skill composer respects tool governance decisions
181:PASS createVllmProvider ignores SYSTEM2_VLLM_* when system2 is false
182:PASS probeVllmServer ignores SYSTEM2_VLLM_* when system2 is false
183:PASS probeVllmServer consults SYSTEM2_VLLM_* when system2 is true
184:PASS probeVllmServer consults SYSTEM2_VLLM_* when nodeId alias resolves to c_lawd
186:PASS resolves with explicit args (highest precedence)
187:PASS falls back to SYSTEM2_VLLM_* env vars
188:PASS falls back to OPENCLAW_VLLM_* env vars
189:PASS prefers SYSTEM2_VLLM_* over OPENCLAW_VLLM_*
190:PASS uses node alias system-2 for c_lawd routing context
191:PASS uses defaults when envs not set
192:PASS emits diagnostic events (keys only)
193:PASS resolves numeric config deterministically
194:PASS invalid numeric env yields NaN (no throw)
196:PASS buildEvidenceBundle captures raw, writes redacted output, and emits manifest
197:PASS buildEvidenceBundle preserves fail-closed snapshot status
199:PASS no-change fixture yields INCONCLUSIVE
200:PASS improvement fixture yields KEEP
201:PASS regression fixture yields REVERT
202:PASS auth preset script maps to calibrated fail-on path
203:PASS calibrated auth fail-on yields REVERT on regression fixture
204:PASS failing subprocess writes UNAVAILABLE report and exits 3
206:PASS FederatedEnvelopeV1 fixture validates (strict)
207:PASS FederatedEnvelopeV1 rejects invalid schema (fail-closed)
208:PASS System2EventV1 fixture validates
209:PASS JSONL sink contract is deterministic (exact line match)
210:PASS redaction-at-write is deterministic and idempotent
211:PASS gating: disabled emitter is a no-op
212:PASS gating: enabled emitter appends a redacted event
213:PASS emitter does not throw on sink error by default (strict=false)
214:PASS emitter fails closed on sink error when strict=true
216:PASS edge rejects missing/invalid auth and does not log secrets
217:PASS edge rate limits per identity
218:PASS edge enforces body size limit (413)
219:PASS rpc routes require approval (fail-closed)
220:PASS malformed read tool payloads are denied at edge
221:PASS websocket upgrade requires approval (fail-closed)
222:PASS non-loopback bind requires explicit opt-in
223:PASS HMAC signing auth (replay resistant)
224:PASS HMAC mode can allow loopback Bearer (opt-in)
225:PASS audit sink writes JSONL and rotates (no secrets)
226:PASS tokens/hmac keys file mode is enforced (0600)
227:PASS inflight caps + timeouts are enforced/configured
230:PASS system2 repair auth-profiles acceptance check
232:PASS system2 repair models acceptance check
234:PASS system2 repair scripts regression gate
236:PASS captureSnapshot writes stable files and summary shape
237:PASS captureSnapshot fail-closed with partial outputs when command fails
239:PASS JSON output is stable and ignores timestamp fields by default
240:PASS ignore list suppresses expected diff paths and exits 0
241:PASS fail-on marks regressions and exits 2
242:PASS human output includes summary counts and regression marker
243:PASS computeDiff supports deterministic dotpath flattening
245:PASS OFF: system2.observability.enabled=false emits nothing and writes no JSONL
246:PASS ON: system2.observability.enabled=true writes exactly one deterministic JSONL line
248:PASS tacticr feedback writer appends schema-valid sanitized JSONL entries
249:PASS tacticr feedback writer enforces required schema fields
251:PASS tool governance allows explicit allowlist actions
252:PASS tool governance asks for exec/network/outside-workspace writes
253:PASS tool governance denies explicit denylist actions
255:PASS http edge governance hook maps approval/deny errors deterministically
256:FAILURES: 1/38
```

## Phase 5 Config Hygiene

```text
$ rg -n ""command""\s*:\s*""python"" -S .

$ git ls-files | rg -n "openclaw\.json"
432:workspace/hivemind/openclaw.json
```

### phase5_post_fix_checks

```text
$ rg -n ""command""\s*:\s*""python"" -S workspace/hivemind/openclaw.json

$ rg -n ""command""\s*:\s*""python3"" -S workspace/hivemind/openclaw.json
5:      "command": "python3",
```

## Phase 6 Permission Hardening

```text
$ ls -l env.d/system1-routing.env || true
-rw-r--r--@ 1 heathyeager  staff  611 Feb 19 16:53 env.d/system1-routing.env

$ git ls-files env.d/system1-routing.env && echo "tracked"
env.d/system1-routing.env
tracked

$ chmod 600 env.d/system1-routing.env || true

$ ls -l env.d/system1-routing.env || true
-rw-------@ 1 heathyeager  staff  611 Feb 19 16:53 env.d/system1-routing.env
```

### python_unittest_q_after_sim_runner_fix

```text
$ python3 -m unittest -q
(exit=0)
moved:
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp1rmm57c0/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp1rmm57c0/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp1rmm57c0/overlay/quarantine/20260220-072558/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpzrx5a7rh/overlay/quarantine/20260220-072559/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpfe3t4e2p/overlay/quarantine/20260220-072559/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp1tb2ymwz/overlay/quarantine/20260220-072559/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpu0btra1d/overlay/quarantine/20260220-072559/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp61sjg6da/overlay/quarantine/20260220-072559/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_test
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp61sjg6da/quarantine/openclaw-quarantine-20260220-072559
```

### npm_test_silent_after_sim_runner_fix

```text
$ npm test --silent
(exit=0)
49:PASS analyze_session_patterns aggregates recurring inefficiency patterns
51:PASS anticipate module emits suggestion-only low-risk automation hints
52:PASS anticipate feature flag disables suggestions
54:PASS ask_first enforces approval for exec
55:PASS ask_first allows ask-decision action with operator approval
56:PASS ask_first surfaces deny decisions as ToolDeniedError
58:PASS audit sink hash chaining persists across rotation
60:PASS starts in closed state with zero usage
61:PASS records usage and decrements remaining
62:PASS trips on token cap exceeded
63:PASS trips on call cap exceeded
64:PASS rejects usage when open
65:PASS canProceed returns false when open
66:PASS canProceed returns false when estimate exceeds remaining
67:PASS reset restores closed state
68:PASS reset with new caps
71:PASS context sanitizer redacts tool-shaped JSON payload
72:PASS context sanitizer strips role/authority prefixes
73:PASS context sanitizer preserves normal human text
91:PASS classifyDispatchError: timeout
92:PASS classifyDispatchError: auth/config/http
94:PASS integrity baseline is deterministic
95:PASS integrity drift fails closed and explicit approval recovers
96:PASS runtime identity override metadata is denied
97:PASS integrity guard hook enforces baseline presence
99:PASS parseAddedLegacyMentions finds newly added System-1 references
100:PASS lintLegacyNames ignores files with legacy header notice
102:PASS memory writer sanitizes and appends workspace memory entries
104:PASS model routing no oauth/codex regression gate
106:PASS returns zero findings when relative require resolves
107:PASS reports finding when relative require target is missing
110:PASS moltbook activity aggregates monthly impact from local stub events
112:PASS loads system map with expected defaults
113:PASS normalizes system1/system-1 aliases to dali
114:PASS normalizes system2/system-2 aliases to c_lawd
115:PASS resolves workspace and memory roots from alias
117:PASS provider_diag includes grep-friendly providers_summary section
120:PASS healthProbe succeeds against mocked vLLM endpoint and normalizes /v1
121:PASS healthProbe returns fail-closed result when endpoint is unreachable
122:PASS generateChat returns expected output shape from vLLM response
123:PASS normalizeBaseUrl appends /v1 only when missing
125:PASS idempotent: applying rules twice yields same result
126:PASS JSON validity preserved after redaction
127:PASS no /Users/ or heathyeager remains after redaction
128:PASS repo root path replaced correctly
129:PASS openclaw config path replaced correctly
130:PASS generic home path replaced correctly
131:PASS ls -la line replaced correctly
132:PASS standalone username replaced
133:PASS timestamps, hashes, exit codes not redacted
134:PASS placeholders are not themselves redactable patterns
135:PASS CLI redacts synthetic fixtures and writes output bundle
136:PASS CLI dry-run emits summary and does not write output files
138:PASS provider mapping exposes required env vars
139:PASS maskSecretFingerprint never returns raw secret value
140:PASS bridge serialization does not expose env secret values
141:PASS injectRuntimeEnv respects operator override and injects missing
142:PASS injectRuntimeEnv propagates GROQ_API_KEY operator override to OPENCLAW_GROQ_API_KEY
143:PASS config includes secrets bridge governance knobs
144:PASS redaction covers mapped secret env vars
145:PASS auto backend detection is platform deterministic
146:PASS file backend requires explicit opt-in
148:PASS secrets cli exec injects alias env keys without printing values
150:PASS plugin registers CLI command: secrets
151:PASS secrets cli status prints enablement header (no secrets)
154:PASS skill composer is disabled by default
155:PASS skill composer respects tool governance decisions
157:PASS createVllmProvider ignores SYSTEM2_VLLM_* when system2 is false
158:PASS probeVllmServer ignores SYSTEM2_VLLM_* when system2 is false
159:PASS probeVllmServer consults SYSTEM2_VLLM_* when system2 is true
160:PASS probeVllmServer consults SYSTEM2_VLLM_* when nodeId alias resolves to c_lawd
162:PASS resolves with explicit args (highest precedence)
163:PASS falls back to SYSTEM2_VLLM_* env vars
164:PASS falls back to OPENCLAW_VLLM_* env vars
165:PASS prefers SYSTEM2_VLLM_* over OPENCLAW_VLLM_*
166:PASS uses node alias system-2 for c_lawd routing context
167:PASS uses defaults when envs not set
168:PASS emits diagnostic events (keys only)
169:PASS resolves numeric config deterministically
170:PASS invalid numeric env yields NaN (no throw)
172:PASS buildEvidenceBundle captures raw, writes redacted output, and emits manifest
173:PASS buildEvidenceBundle preserves fail-closed snapshot status
175:PASS no-change fixture yields INCONCLUSIVE
176:PASS improvement fixture yields KEEP
177:PASS regression fixture yields REVERT
178:PASS auth preset script maps to calibrated fail-on path
179:PASS calibrated auth fail-on yields REVERT on regression fixture
180:PASS failing subprocess writes UNAVAILABLE report and exits 3
182:PASS FederatedEnvelopeV1 fixture validates (strict)
183:PASS FederatedEnvelopeV1 rejects invalid schema (fail-closed)
184:PASS System2EventV1 fixture validates
185:PASS JSONL sink contract is deterministic (exact line match)
186:PASS redaction-at-write is deterministic and idempotent
187:PASS gating: disabled emitter is a no-op
188:PASS gating: enabled emitter appends a redacted event
189:PASS emitter does not throw on sink error by default (strict=false)
190:PASS emitter fails closed on sink error when strict=true
192:PASS edge rejects missing/invalid auth and does not log secrets
193:PASS edge rate limits per identity
194:PASS edge enforces body size limit (413)
195:PASS rpc routes require approval (fail-closed)
196:PASS malformed read tool payloads are denied at edge
197:PASS websocket upgrade requires approval (fail-closed)
198:PASS non-loopback bind requires explicit opt-in
199:PASS HMAC signing auth (replay resistant)
200:PASS HMAC mode can allow loopback Bearer (opt-in)
201:PASS audit sink writes JSONL and rotates (no secrets)
202:PASS tokens/hmac keys file mode is enforced (0600)
203:PASS inflight caps + timeouts are enforced/configured
206:PASS system2 repair auth-profiles acceptance check
208:PASS system2 repair models acceptance check
210:PASS system2 repair scripts regression gate
212:PASS captureSnapshot writes stable files and summary shape
213:PASS captureSnapshot fail-closed with partial outputs when command fails
215:PASS JSON output is stable and ignores timestamp fields by default
216:PASS ignore list suppresses expected diff paths and exits 0
217:PASS fail-on marks regressions and exits 2
218:PASS human output includes summary counts and regression marker
219:PASS computeDiff supports deterministic dotpath flattening
221:PASS OFF: system2.observability.enabled=false emits nothing and writes no JSONL
222:PASS ON: system2.observability.enabled=true writes exactly one deterministic JSONL line
224:PASS tacticr feedback writer appends schema-valid sanitized JSONL entries
225:PASS tacticr feedback writer enforces required schema fields
227:PASS tool governance allows explicit allowlist actions
228:PASS tool governance asks for exec/network/outside-workspace writes
229:PASS tool governance denies explicit denylist actions
231:PASS http edge governance hook maps approval/deny errors deterministically
```

## Phase 7 Final Regression

### git_status_porcelain_final

```text
$ git status --porcelain -uall
(exit=0)
 M .claude/worktrees/crazy-brahmagupta
 M .claude/worktrees/elastic-swirles
 M memory/2026-02-19.md
 M workspace/audit/system_audit_fixes_20260219T211622Z.md
 M workspace/state/tacti_cr/events.jsonl
?? nodes/ain/IDENTITY.md
?? nodes/ain/MEMORY.md
?? nodes/ain/docs/AIN_FRAMEWORK.md
?? nodes/ain/docs/README.md
?? nodes/ain/docs/RESEARCH_JOURNEY.md
?? nodes/ain/research/PAPERS.md
```

### python_unittest_q_final

```text
$ python3 -m unittest -q
(exit=0)
----------------------------------------------------------------------
Ran 107 tests in 3.402s

OK
system2_stray_auto_ingest: ok
moved:
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmplxx8yc8k/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmplxx8yc8k/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmplxx8yc8k/overlay/quarantine/20260220-072628/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp9n8gjm4b/overlay/quarantine/20260220-072629/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp78ct6mqo/overlay/quarantine/20260220-072629/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpdxk3d2by/overlay/quarantine/20260220-072630/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmps7lvww0a/overlay/quarantine/20260220-072630/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpd4nobmsm/overlay/quarantine/20260220-072630/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_test
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpd4nobmsm/quarantine/openclaw-quarantine-20260220-072630
```

### npm_test_silent_final

```text
$ npm test --silent
(exit=0)
PASS normalizes system1/system-1 aliases to dali
PASS normalizes system2/system-2 aliases to c_lawd
PASS resolves workspace and memory roots from alias
RUN node tests/provider_diag_format.test.js
PASS provider_diag includes grep-friendly providers_summary section
provider_diag_format tests complete
RUN node tests/providers/local_vllm_provider.test.js
PASS healthProbe succeeds against mocked vLLM endpoint and normalizes /v1
PASS healthProbe returns fail-closed result when endpoint is unreachable
PASS generateChat returns expected output shape from vLLM response
PASS normalizeBaseUrl appends /v1 only when missing
RUN node tests/redact_audit_evidence.test.js
PASS idempotent: applying rules twice yields same result
PASS JSON validity preserved after redaction
PASS no /Users/ or heathyeager remains after redaction
PASS repo root path replaced correctly
PASS openclaw config path replaced correctly
PASS generic home path replaced correctly
PASS ls -la line replaced correctly
PASS standalone username replaced
PASS timestamps, hashes, exit codes not redacted
PASS placeholders are not themselves redactable patterns
PASS CLI redacts synthetic fixtures and writes output bundle
PASS CLI dry-run emits summary and does not write output files
RUN node tests/secrets_bridge.test.js
PASS provider mapping exposes required env vars
PASS maskSecretFingerprint never returns raw secret value
PASS bridge serialization does not expose env secret values
PASS injectRuntimeEnv respects operator override and injects missing
PASS injectRuntimeEnv propagates GROQ_API_KEY operator override to OPENCLAW_GROQ_API_KEY
PASS config includes secrets bridge governance knobs
PASS redaction covers mapped secret env vars
PASS auto backend detection is platform deterministic
PASS file backend requires explicit opt-in
RUN node tests/secrets_cli_exec.test.js
PASS secrets cli exec injects alias env keys without printing values
RUN node tests/secrets_cli_plugin.test.js
PASS plugin registers CLI command: secrets
PASS secrets cli status prints enablement header (no secrets)
secrets_cli_plugin tests complete
RUN node tests/skill_composer.test.js
PASS skill composer is disabled by default
PASS skill composer respects tool governance decisions
RUN node tests/system1_ignores_system2_env.test.js
PASS createVllmProvider ignores SYSTEM2_VLLM_* when system2 is false
PASS probeVllmServer ignores SYSTEM2_VLLM_* when system2 is false
PASS probeVllmServer consults SYSTEM2_VLLM_* when system2 is true
PASS probeVllmServer consults SYSTEM2_VLLM_* when nodeId alias resolves to c_lawd
RUN node tests/system2_config_resolver.test.js
PASS resolves with explicit args (highest precedence)
PASS falls back to SYSTEM2_VLLM_* env vars
PASS falls back to OPENCLAW_VLLM_* env vars
PASS prefers SYSTEM2_VLLM_* over OPENCLAW_VLLM_*
PASS uses node alias system-2 for c_lawd routing context
PASS uses defaults when envs not set
PASS emits diagnostic events (keys only)
PASS resolves numeric config deterministically
PASS invalid numeric env yields NaN (no throw)
RUN node tests/system2_evidence_bundle.test.js
PASS buildEvidenceBundle captures raw, writes redacted output, and emits manifest
PASS buildEvidenceBundle preserves fail-closed snapshot status
RUN node tests/system2_experiment.test.js
PASS no-change fixture yields INCONCLUSIVE
PASS improvement fixture yields KEEP
PASS regression fixture yields REVERT
PASS auth preset script maps to calibrated fail-on path
PASS calibrated auth fail-on yields REVERT on regression fixture
PASS failing subprocess writes UNAVAILABLE report and exits 3
RUN node tests/system2_federation_observability_contract.test.js
PASS FederatedEnvelopeV1 fixture validates (strict)
PASS FederatedEnvelopeV1 rejects invalid schema (fail-closed)
PASS System2EventV1 fixture validates
PASS JSONL sink contract is deterministic (exact line match)
PASS redaction-at-write is deterministic and idempotent
PASS gating: disabled emitter is a no-op
PASS gating: enabled emitter appends a redacted event
PASS emitter does not throw on sink error by default (strict=false)
PASS emitter fails closed on sink error when strict=true
RUN node tests/system2_http_edge.test.js
PASS edge rejects missing/invalid auth and does not log secrets
PASS edge rate limits per identity
PASS edge enforces body size limit (413)
PASS rpc routes require approval (fail-closed)
PASS malformed read tool payloads are denied at edge
PASS websocket upgrade requires approval (fail-closed)
PASS non-loopback bind requires explicit opt-in
PASS HMAC signing auth (replay resistant)
PASS HMAC mode can allow loopback Bearer (opt-in)
PASS audit sink writes JSONL and rotates (no secrets)
PASS tokens/hmac keys file mode is enforced (0600)
PASS inflight caps + timeouts are enforced/configured
system2_http_edge tests complete
RUN node tests/system2_repair_auth_profiles_acceptance.test.js
PASS system2 repair auth-profiles acceptance check
RUN node tests/system2_repair_models_acceptance.test.js
PASS system2 repair models acceptance check
RUN node tests/system2_repair_scripts_regression.test.js
PASS system2 repair scripts regression gate
RUN node tests/system2_snapshot_capture.test.js
PASS captureSnapshot writes stable files and summary shape
PASS captureSnapshot fail-closed with partial outputs when command fails
RUN node tests/system2_snapshot_diff.test.js
PASS JSON output is stable and ignores timestamp fields by default
PASS ignore list suppresses expected diff paths and exits 0
PASS fail-on marks regressions and exits 2
PASS human output includes summary counts and regression marker
PASS computeDiff supports deterministic dotpath flattening
RUN node tests/system2_snapshot_observability_seam.test.js
PASS OFF: system2.observability.enabled=false emits nothing and writes no JSONL
PASS ON: system2.observability.enabled=true writes exactly one deterministic JSONL line
RUN node tests/tacticr_feedback_writer.test.js
PASS tacticr feedback writer appends schema-valid sanitized JSONL entries
PASS tacticr feedback writer enforces required schema fields
RUN node tests/tool_governance.test.js
PASS tool governance allows explicit allowlist actions
PASS tool governance asks for exec/network/outside-workspace writes
PASS tool governance denies explicit denylist actions
RUN node tests/tool_governance_edge_hook.test.js
PASS http edge governance hook maps approval/deny errors deterministically
OK 38 test group(s)
```

## Fix Summary

- `workspace/scripts/policy_router.py`:
  - Restored compatibility API symbols expected by tests:
    - `PolicyValidationError`
    - `ACTIVE_INFERENCE_STATE_PATH`
    - `tacti_enhance_plan`
  - Added strict-by-default policy schema key validation (with `OPENCLAW_POLICY_STRICT=0` escape hatch) so typo/unknown-key tests fail closed as expected.
  - Wired active inference metadata persistence into routing when `ENABLE_ACTIVE_INFERENCE=1`.
  - Wired TACTI main-flow hook invocation only when dynamics flags are enabled, including `tacti_routing_plan` event emission and stable `result.tacti` payload.

- `workspace/policy/llm_policy.json`:
  - Set `routing.free_order` to the canonical no-oauth ladder expected by invariant and regression gates.
  - Updated `routing.intents.governance` and `routing.intents.security` to the same free ladder with `allowPaid=false`.
  - Added `routing.intents.system2_audit` with the same free ladder and `allowPaid=false`.
  - Disabled `providers.openai_auth.enabled` and `providers.openai_api.enabled` to satisfy no-oauth policy expectations.

- `package.json`:
  - Added Jest `testPathIgnorePatterns` for `/.claude/worktrees/` to prevent mirrored worktree tests from polluting targeted `npx jest` runs.

- `tests/model_routing_no_oauth.test.js`:
  - Added a minimal Jest compatibility wrapper so the same file works under both direct `node` execution and `jest` (`test(...)`), avoiding "must contain at least one test" failures.

- `scripts/sim_runner.py`:
  - Removed import-time hard exit on missing `pyyaml`; now defers failure to `load_config()` call sites.
  - This unblocks unit test import paths that only need `compute_sim_b_tilt`.

## Post-Fix Results

- Final regression commands all pass:
  - `git status --porcelain -uall`
  - `python3 -m unittest -q`
  - `npm test --silent`

## Non-Blocking Follow-Ups

- Branch pruning and stash hygiene intentionally left as non-goals per request.
- Optional: if runtime sim execution is needed on this host, install `pyyaml` (`pip install pyyaml`) to enable YAML config loading in `scripts/sim_runner.py` runtime paths.
