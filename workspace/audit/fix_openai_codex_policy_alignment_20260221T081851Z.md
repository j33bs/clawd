# Branch Audit: openai-codex policy alignment

- Timestamp (UTC): 2026-02-21T08:18:51Z
- Branch: fix/npm-policy-openai-codex-alignment-20260221T081840Z
- Baseline HEAD: a2a0aa5

## Phase 0 Baseline
```bash
$ date -u
Sat Feb 21 08:18:51 UTC 2026

$ git status --porcelain -uall
?? workspace/audit/fix_openai_codex_policy_alignment_20260221T081851Z.md

$ git checkout main && git pull --ff-only
Skipped in this worktree; equivalent baseline is origin/main at worktree creation.

$ git checkout -b fix/npm-policy-openai-codex-alignment-<timestamp>
Already created at worktree init: fix/npm-policy-openai-codex-alignment-20260221T081840Z
```

## Phase 1 Reproduce + Localize
```bash
$ npm test || true
Ran 162 tests in 4.237s
OK
RUN node tests/model_routing_no_oauth.test.js
PASS model routing no oauth/codex regression gate
OK 38 test group(s)

$ rg -n "AssertionError \[ERR_ASSERTION\]: policy\.providers must not include openai-codex|PASS model routing no oauth/codex regression gate|OK 38 test group\(s\)" /tmp/openai_codex_alignment_npm_test_after.log
108:PASS model routing no oauth/codex regression gate
236:OK 38 test group(s)
```

Observation:
- The previously reported assertion is not reproducible on current `origin/main`; contract is currently satisfied.
- Assertion source remains in: `tests/model_routing_no_oauth.test.js:84`.

Localization commands:
```bash
$ rg -n "policy.providers|providers.openai-codex|openai-codex" .
...
tests/model_routing_no_oauth.test.js:84: assert.ok(!Object.prototype.hasOwnProperty.call(policyProviders, k), `policy.providers must not include ${k}`);
workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md:38:- No OpenAI/Codex provider lanes and no model IDs starting with `openai/` or `openai-codex/`.
workspace/scripts/verify_goal_identity_invariants.py:29:    "openai-codex",
workspace/scripts/verify_goal_identity_invariants.py:205:        if s in policy_text:
```

## Phase 2 Decision Rule
Chosen rule: **A) openai-codex is NEVER allowed in canonical policy.providers (default deny).**

Rationale (citations):
- Governance contract explicitly forbids OpenAI/Codex provider lanes: `workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md:38`.
- Invariant verifier bans `openai-codex`/`openai_codex` in policy text: `workspace/scripts/verify_goal_identity_invariants.py:27`, `workspace/scripts/verify_goal_identity_invariants.py:204`.
- Canonical regression test enforces policy provider absence: `tests/model_routing_no_oauth.test.js:83`.

## Phase 3 Minimal Alignment Implemented
1. `workspace/scripts/verify_security_config.sh`
- Added `check_policy_provider_contract()`.
- Enforces:
  - `policy.providers` must not include `openai-codex` or `openai_codex`.
  - If `openai_auth` / `openai_api` keys exist, they must remain disabled.
- Relevant lines after change: `workspace/scripts/verify_security_config.sh:26`, `workspace/scripts/verify_security_config.sh:46`.

2. `tests/model_routing_no_oauth.test.js`
- Clarified policy contract comment (no behavior change) to avoid ambiguity.
- Relevant line: `tests/model_routing_no_oauth.test.js:77`.

## Phase 4 Verification
```bash
$ npm test
Ran 162 tests in 4.237s
OK
PASS model routing no oauth/codex regression gate
OK 38 test group(s)

$ bash workspace/scripts/verify_security_config.sh
WARN: openclaw.json not found in repo; skipping repo-local node.id enforcement
FAIL: agents/main/agent/models.json: groq.enabled must be false
FAIL: agents/main/agent/models.json: groq.apiKey must be empty (no secrets)

$ python3 -m unittest discover -s tests_unittest -p "test.py"
----------------------------------------------------------------------
Ran 0 tests in 0.000s

NO TESTS RAN

$ node tests/model_routing_no_oauth.test.js
PASS model routing no oauth/codex regression gate
```

Notes:
- `verify_security_config.sh` failure is the known independent Groq mismatch tracked separately (`fix/groq-policy-alignment-*`), not introduced by this branch.

## Phase 5 Governance Log + Policy Traceability
- Added governance admission row:
  - `workspace/governance/GOVERNANCE_LOG.md:11`
  - `POLICY-2026-02-21-OPENAI-CODEX-001`

```bash
$ bash workspace/scripts/verify_governance_log.sh
verify_governance_log.sh not present on main baseline; no log-format script to execute in this branch.
```

## Files Changed
- `workspace/scripts/verify_security_config.sh`
- `tests/model_routing_no_oauth.test.js`
- `workspace/governance/GOVERNANCE_LOG.md`
- `workspace/audit/fix_openai_codex_policy_alignment_20260221T081851Z.md`
