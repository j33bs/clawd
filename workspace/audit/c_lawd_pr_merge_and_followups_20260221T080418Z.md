# C_Lawd PR Merge + Follow-ups

## Baseline
```bash
date -u
Sat Feb 21 08:04:18 UTC 2026

git rev-parse --short HEAD
a2a0aa5

git status --porcelain -uall
?? workspace/audit/c_lawd_pr_merge_and_followups_20260221T080418Z.md
```

## Evidence Pointers
- Remediation branch: codex/audit/c_lawd-full-remediation-20260221T064620Z
- Remediation audit doc: workspace/audit/c_lawd_full_audit_remediation_20260221T070817Z.md (on remediation branch)

## Plan
1. Generate merge-ready PR narrative with explicit evidence and pre-existing failure attribution.
2. Create follow-up branch A for canonical SOUL drift and make the unittest green.
3. Create follow-up branch B for regression bootstrap config contract (openclaw.json absence).
4. Create follow-up branch C for Groq policy/verifier alignment and make verifier green.

## Remediation Audit Summary

Commit range on remediation branch (717e29c..codex/audit/c_lawd-full-remediation-20260221T064620Z):
```text
7c85c6c sec(integrity): remove verifyOnce bypass; always verify
cbec800 sec(provider): move Gemini key to header; no query secrets
659b5b7 sec(audit): verify hash chain on read + tamper test
e2f1510 gov: enforce/update GOVERNANCE_LOG + policy hook/script
3da0743 sec(secrets): fix passphrase handling path
38c50ea sec(paths): realpath containment check for workspace boundary
22a09ac chore(workspace): resolve untracked files + BOOTSTRAP.md
fbcdcc2 fix(router): resolve or gate OAuth 401
4d71418 ops(source-ui): remove secrets, absolute paths, root requirement
e5f448e test(redaction): scrub scanner-noise placeholders
bb37061 docs(audit): full evidence + snapshot table
```

Exact pre-existing failing-gate excerpts (from remediation verification logs):
```text
FAIL: repo-root governance file diverges from canonical: SOUL.md
AssertionError [ERR_ASSERTION]: policy.providers must not include openai-codex
✗ FAIL: openclaw config not found for provider gating check
FAIL: agents/main/agent/models.json: groq.enabled must be false
FAIL: agents/main/agent/models.json: groq.apiKey must be empty (no secrets)
```

Root-cause pointers:
- Canonical SOUL mirror enforcement: `/private/tmp/clawd-followups-20260221T080402Z/workspace/scripts/verify_goal_identity_invariants.py:18` and `/private/tmp/clawd-followups-20260221T080402Z/workspace/scripts/verify_goal_identity_invariants.py:183`
- Failing SOUL unittest assertion harness: `/private/tmp/clawd-followups-20260221T080402Z/tests_unittest/test_goal_identity_invariants.py:21`
- Regression openclaw config contract check: `/private/tmp/clawd-followups-20260221T080402Z/workspace/scripts/regression.sh:209` and `/private/tmp/clawd-followups-20260221T080402Z/workspace/scripts/regression.sh:263`
- Groq verifier mismatch rules: `/private/tmp/clawd-followups-20260221T080402Z/workspace/scripts/verify_security_config.sh:21`, `/private/tmp/clawd-followups-20260221T080402Z/workspace/scripts/verify_security_config.sh:23`, `/private/tmp/clawd-followups-20260221T080402Z/workspace/scripts/verify_security_config.sh:46`
- Routing policy mismatch assertion in npm test: `/private/tmp/clawd-followups-20260221T080402Z/tests/model_routing_no_oauth.test.js:84`

## Executed Commands
```bash
git log --oneline --reverse 717e29c..codex/audit/c_lawd-full-remediation-20260221T064620Z
git show codex/audit/c_lawd-full-remediation-20260221T064620Z:workspace/audit/c_lawd_full_audit_remediation_20260221T070817Z.md
nl -ba workspace/scripts/verify_goal_identity_invariants.py
nl -ba workspace/scripts/regression.sh
nl -ba workspace/scripts/verify_security_config.sh
nl -ba tests/model_routing_no_oauth.test.js
```

Key output excerpts:
```text
$ git log --oneline --reverse 717e29c..codex/audit/c_lawd-full-remediation-20260221T064620Z
7c85c6c sec(integrity): remove verifyOnce bypass; always verify
cbec800 sec(provider): move Gemini key to header; no query secrets
659b5b7 sec(audit): verify hash chain on read + tamper test
...
bb37061 docs(audit): full evidence + snapshot table

$ git show codex/audit/c_lawd-full-remediation-20260221T064620Z:workspace/audit/c_lawd_full_audit_remediation_20260221T070817Z.md | rg -n "FAIL:|AssertionError"
... FAIL: repo-root governance file diverges from canonical: SOUL.md
... AssertionError [ERR_ASSERTION]: policy.providers must not include openai-codex
... ✗ FAIL: openclaw config not found for provider gating check
... FAIL: agents/main/agent/models.json: groq.enabled must be false
... FAIL: agents/main/agent/models.json: groq.apiKey must be empty (no secrets)
```

## Phase 1 PR Prep

```bash
cat > workspace/audit/pr_body_c_lawd_full_remediation_20260221.md
created: workspace/audit/pr_body_c_lawd_full_remediation_20260221.md
```
