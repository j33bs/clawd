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

