# Branch Protection Follow-up

## Observed Behavior
Direct pushes to `main` succeeded while remote output still reported bypassed requirements (PR-only policy and expected CI check).

## Risk
Unvalidated commits can land on `main`, bypassing deterministic test gates and review controls.

## Recommended Remediation
- Enforce branch protection on `main` with pull-request-only merges.
- Require passing status checks before merge (at minimum: `ci` and `node-test`).
- Block force-push and branch deletion for `main`.
- Restrict bypass permissions to audited break-glass operators.
