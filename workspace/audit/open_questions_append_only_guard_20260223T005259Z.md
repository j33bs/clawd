# OPEN_QUESTIONS Append-Only Guard Evidence (20260223T005259Z)

## Commands
- bash workspace/scripts/tests/test_guard_open_questions_append_only.sh

## Output
```text
```

## Notes
- Guard enforces: HEAD content must be exact prefix of staged OPEN_QUESTIONS.md.
- Bypass requires OPENCLAW_GOV_BYPASS=1 and logs warning to stderr.
