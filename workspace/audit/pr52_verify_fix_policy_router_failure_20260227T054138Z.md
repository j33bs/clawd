# PR52 verify fix — verify_policy_router failure capture
timestamp_utc: 20260227T054138Z

## Command
- bash workspace/scripts/verify_policy_router.sh

## Output
Traceback (most recent call last):
  File "<stdin>", line 413, in <module>
  File "<stdin>", line 404, in main
  File "<stdin>", line 190, in test_budget_enforcement_and_token_cap
AssertionError: {'ok': False, 'reason_code': 'intent_call_budget_exhausted', 'attempts': 1, 'request_id': 'rt-19c9d9e3975-1006543b', 'capability_class': 'planning_synthesis'}

exit_code: 1
