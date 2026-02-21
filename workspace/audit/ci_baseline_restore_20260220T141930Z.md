# CI baseline restore

Base: origin/main

HEAD: e8ad6d7

## Baseline failure capture

Commands:

```bash
python3 -m unittest -q > /tmp/ci_fix_py.txt 2>&1 || true
npm test --silent > /tmp/ci_fix_npm.txt 2>&1 || true
```

Python failure signatures (excerpt):

```text
ImportError: cannot import name 'cache_epitope' from 'tacti_cr.semantic_immune'
KeyError: 'meta'
ImportError: cannot import name 'autocommit_opt_in_signal' from 'team_chat'
AttributeError: module 'team_chat' has no attribute 'run_multi_agent'
ImportError: cannot import name 'surprise_score_proxy' from 'workspace.tacti_cr.temporal'
AttributeError: policy_router has no attribute 'WITNESS_LEDGER_PATH'
FAILED (failures=5, errors=8)
```

npm failure signature:

```text
FAILURES: 1/38
```

## Fixes applied (compatibility shims + schema defaults)

1. `workspace/tacti_cr/semantic_immune.py`
- Added `EpitopeCache`, module cache `_EPITOPE_CACHE`, `cache_epitope(...)`, and `epitope_cache_hit(...)`.
- Kept behavior gated by `OPENCLAW_SEMANTIC_IMMUNE_EPITOPES` / `OPENCLAW_EPITOPE_CACHE`.

2. `workspace/tacti_cr/temporal.py`
- Added deterministic helpers `text_embedding_proxy(...)` and `surprise_score_proxy(...)`.
- Added flag-gated surprise gate path in `TemporalMemory.store(...)` behind `OPENCLAW_TEMPORAL_SURPRISE_GATE` / `OPENCLAW_SURPRISE_GATE`.

3. `workspace/scripts/team_chat.py`
- Added `autocommit_opt_in_signal(...)` and `teamchat_user_directed_signal(...)` exports.
- Added `run_multi_agent(...)` compatibility entrypoint.
- Updated `auto_commit_changes(...)` to preserve dual opt-in contract and return `(commit_sha, audit_path)` tuple expected by tests.

4. `workspace/scripts/policy_router.py`
- Added `WITNESS_LEDGER_PATH` export.
- Added `canonical_intent(...)` mapping for `teamchat:*` budget/routing compatibility.
- Added `meta.proprioception` emission when router proprioception flag is enabled.
- Added handler alias fallback and preserved expected `google-gemini-cli` identity in TACTI plan output.
- Added `tacti_features_from_proprioception(...)` compatibility adaptor to keep arousal defaults deterministic.

## npm failing suite triage

`npm test --silent` failure `FAILURES: 1/38` originated from the Python unittest stage run by `tests/run_tests.js`:

```text
RUN python3  -m unittest discover -s tests_unittest -p test_*.py
...
FAILED (failures=5, errors=8)
...
FAILURES: 1/38
```

No standalone JS suite regression was present; fixing the Python interface/schema failures restored npm pass.

## Post-fix verification

Commands run:

```bash
python3 -m unittest -q > /tmp/ci_fix_py_post.txt 2>&1
npm test --silent > /tmp/ci_fix_npm_post.txt 2>&1
python3 workspace/scripts/verify_goal_identity_invariants.py > /tmp/ci_fix_identity_post.txt 2>&1
```

Outcomes:

```text
python3 -m unittest -q: PASS (exit 0)
npm test --silent: PASS (exit 0)
python3 workspace/scripts/verify_goal_identity_invariants.py: PASS (exit 0)
```

## Final gate confirmation

```bash
python3 -m unittest -q
npm test --silent
python3 workspace/scripts/verify_goal_identity_invariants.py
```

Result: all PASS on this branch.

Note: `workspace/state/tacti_cr/events.jsonl` is a tracked runtime file and was re-dirtied by tests; it was restored with `git checkout -- workspace/state/tacti_cr/events.jsonl` before commit so this PR remains interface/default-only.
