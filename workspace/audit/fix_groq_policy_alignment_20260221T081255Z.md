# Branch Audit: groq policy alignment

- Timestamp (UTC): 2026-02-21T08:12:55Z
- Branch: fix/groq-policy-alignment-20260221T081156Z
- Head: a2a0aa5

## Baseline
```bash
$ date -u
Sat Feb 21 08:12:55 UTC 2026
$ git rev-parse --short HEAD
a2a0aa5
$ git status --porcelain -uall
 M workspace/scripts/verify_security_config.sh
?? workspace/audit/c_lawd_pr_merge_and_followups_20260221T080418Z.md
?? workspace/audit/fix_groq_policy_alignment_20260221T081255Z.md
?? workspace/audit/pr_body_c_lawd_full_remediation_20260221.md
```

## Reproduction (pre-fix)
```bash
$ bash workspace/scripts/verify_security_config.sh || true
WARN: openclaw.json not found in repo; skipping repo-local node.id enforcement
FAIL: agents/main/agent/models.json: groq.enabled must be false
FAIL: agents/main/agent/models.json: groq.apiKey must be empty (no secrets)
```

## Root Cause
- Verifier expectation was stale and contradicted canonical policy/contracts:
  - `workspace/policy/llm_policy.json` keeps Groq enabled in free ladder with `apiKeyEnv`
  - `tests/model_routing_no_oauth.test.js` asserts Groq is not disabled and uses env-var placeholder
- Stale checks were in `workspace/scripts/verify_security_config.sh` (groq.enabled=false and apiKey empty).

## Change
- Updated `workspace/scripts/verify_security_config.sh` Groq checks to:
  - Reject `enabled=false` (Groq must remain available per policy)
  - Allow only env-var references in `apiKey` (e.g., `GROQ_API_KEY`, `${ENV_VAR_NAME}`)
  - Reject non-placeholder key material

## Verification
```bash
$ bash workspace/scripts/verify_security_config.sh
WARN: openclaw.json not found in repo; skipping repo-local node.id enforcement
ok
$ node tests/model_routing_no_oauth.test.js
PASS model routing no oauth/codex regression gate
```

## Outcome
- Security verifier now matches intended Groq governance and still enforces no committed secret material.
