# fix(dali/payload): close gateway edge bypass; enforce tool payload invariant at final dispatch (strict opt-in)

## Summary
This PR enforces one payload invariant across Dali and gateway final boundaries:
- if `tools` is absent/empty/non-list => `tool_choice` is removed
- if model/provider tool-call capability is unsupported or unknown => remove both (`fail closed`)
- never inject `tool_choice: "none"`

## What Changed
- Fixed raw gateway edge bypass path in `scripts/system2_http_edge.js` by enforcing final-dispatch sanitization at proxy boundary (`gateway.edge.final_dispatch`).
- Enforced canonical final-boundary guards at:
  - `policy_router.final_dispatch` (Python Dali path)
  - `gateway.adapter.final_dispatch` (Node provider adapters)
- Added strict-mode diagnostics (`OPENCLAW_STRICT_TOOL_PAYLOAD=1`):
  - invalid `tool_choice` shape now raises structured bypass errors with:
    - `provider_id`
    - `model_id`
    - `callsite_tag`
    - remediation text
  - with strict mode off, logs structured warnings and sanitizes.

## Runtime Identity Helper
To prove runtime/module identity and detect stale code loading:
- `python3 workspace/scripts/diagnose_tool_payload_runtime.py`

This prints:
- absolute module path for `policy_router`
- absolute module path for `tool_payload_sanitizer`
- git SHA (best effort)
- strict-mode env state

## Tests Run
- `python3 -m py_compile workspace/scripts/tool_payload_sanitizer.py workspace/scripts/policy_router.py workspace/scripts/diagnose_tool_payload_runtime.py`
- `python3 -m unittest tests_unittest.test_policy_router_tool_payload_sanitizer`
- `node tests/providers/tool_payload_sanitizer.test.js`
- `node tests/providers/provider_adapter_tool_payload.test.js`
- `node tests/providers/local_vllm_provider.test.js`

## Evidence
- `workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md`
