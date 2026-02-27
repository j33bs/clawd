# Branch protection enforcement — regression required on main

timestamp_utc: 20260227T055447Z

Intent
- Ensure GitHub branch protection for `main` requires the regression workflow check.

Commands
- gh api repos/j33bs/clawd/branches/main/protection/required_status_checks (read)
- gh api -X PATCH repos/j33bs/clawd/branches/main/protection/required_status_checks -F strict=false -f contexts[]=ci -f contexts[]=regression

Before
```json
{"url":"https://api.github.com/repos/j33bs/clawd/branches/main/protection/required_status_checks","strict":false,"contexts":["ci"],"contexts_url":"https://api.github.com/repos/j33bs/clawd/branches/main/protection/required_status_checks/contexts","checks":[{"context":"ci","app_id":15368}]}
```

After
```json
{"url":"https://api.github.com/repos/j33bs/clawd/branches/main/protection/required_status_checks","strict":false,"contexts":["ci","regression"],"contexts_url":"https://api.github.com/repos/j33bs/clawd/branches/main/protection/required_status_checks/contexts","checks":[{"context":"ci","app_id":15368},{"context":"regression","app_id":15368}]}
```

Result
- required_status_checks.contexts now includes: `ci`, `regression`.

Rollback
- Remove `regression` from required checks:
  gh api -X PATCH repos/j33bs/clawd/branches/main/protection/required_status_checks \
    -F strict=false \
    -f contexts[]=ci
