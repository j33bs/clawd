# System Stability Merge Attempt + Compatibility Fix

- PR: https://github.com/j33bs/clawd/pull/31
- Base: `main`
- Original merge-resolution commit: `c598edb`
- Fix branch: `codex/fix/pr31-mergeable-from-main`

## Post-merge gate failures

Command:
- `npm test`

Key failure traces:
- `AttributeError: module 'preflight_check' has no attribute '_KNOWN_GOV_ROOT_STRAYS'`
- `AttributeError: module 'preflight_check' has no attribute '_auto_ingest_known_gov_root_strays'`
- `AttributeError: module 'preflight_check' has no attribute '_untracked_paths'`
- `AttributeError: module 'preflight_check' has no attribute '_auto_ingest_known_system2_strays'`
- `AssertionError: ... policy routing.free_order must be ['google-gemini-cli', 'qwen-portal', 'groq', 'ollama']`
- `AssertionError [ERR_ASSERTION]: policy.providers.openai_auth.enabled must be false`
- `ModuleNotFoundError: No module named 'yaml'`

## Resolution decisions

### Fix set A (preflight compatibility API)
- Restored tested compatibility symbols and helpers in `workspace/scripts/preflight_check.py`:
  - `_KNOWN_GOV_ROOT_STRAYS`
  - `_untracked_paths`
  - `_auto_ingest_known_gov_root_strays`
  - `_auto_ingest_known_system2_strays`
- Preserved mainline node-id normalization check by keeping `SYSTEM_MAP_FILE` + `check_node_identity` wiring.

Verification:
- `python3 -m unittest -v tests_unittest/test_governance_auto_ingest.py` -> PASS

### Fix set B (policy invariants)
- Restored `workspace/policy/llm_policy.json` to the PR-side expected invariant-compatible ladder:
  - `routing.free_order = ['google-gemini-cli', 'qwen-portal', 'groq', 'ollama']`
  - no enabled OpenAI auth/API lanes for no-oauth regression gate

Verification:
- `python3 -m unittest -v tests_unittest/test_goal_identity_invariants.py` -> PASS
- `node tests/model_routing_no_oauth.test.js` -> PASS

### Fix set C (PyYAML availability for CI)
- Added Python setup + PyYAML install in CI node-test workflow:
  - `.github/workflows/node_test.yml`
  - `actions/setup-python@v5`
  - `python3 -m pip install pyyaml`

Local verification:
- `python3 -c "import yaml; print('pyyaml ok')"` -> PASS
- `python3 -m unittest -v tests_unittest/test_itc_pipeline.py` -> PASS

## Full gate rerun

- `npm test` -> PASS
- `bash workspace/scripts/verify_tacti_system.sh` -> PASS

## Note

- This fix is compatibility-focused for mergeability on top of `c598edb`.
- No new System Stability Bundle features were added.
