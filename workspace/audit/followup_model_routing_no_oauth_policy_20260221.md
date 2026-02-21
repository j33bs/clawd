# Follow-up Scope: Model Routing No-OAuth Policy Drift

- Branch: `fix/model-routing-no-oauth-policy-20260221`
- Scope: repair policy/free-order drift causing `model_routing_no_oauth` failures; no TeamChat/scaffold edits.

## Acceptance Criterion

`node --test tests/model_routing_no_oauth.test.js`

Pass condition: `tests/model_routing_no_oauth.test.js` passes.
