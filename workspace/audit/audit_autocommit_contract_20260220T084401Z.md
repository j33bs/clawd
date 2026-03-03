# TeamChat Auto-commit Contract Audit

## Scope
- Repo: `/Users/heathyeager/clawd`
- Branch: `codex/feature/evolution-ideas-1-10-20260220`
- Objective: verify and enforce explicit opt-in + self-auditing auto-commit governance.

## 1) Auto-committer location
- Primary implementation: `workspace/scripts/team_chat.py`
- Verification entrypoint: `workspace/scripts/verify_team_chat.sh`

### Discovery commands
```bash
rg -n "auto-commit|autocommit|git commit|cycle [0-9]+ accepted patch|verify_team_chat" -S workspace/scripts workspace/teamchat workspace
```

### Findings
- Auto-commit previously happened in `auto_commit_changes(...)` on accepted planner decision.
- Previous behavior had no explicit opt-in gate and staged all changes (`git add -A`).

## 2) Explicit opt-in contract (implemented)
Implemented in `workspace/scripts/team_chat.py`:
- `teamchat_user_directed_signal(args)`
  - requires one of:
    - CLI: `--user-directed-teamchat`
    - ENV: `TEAMCHAT_USER_DIRECTED_TEAMCHAT=1`
- `autocommit_opt_in_signal(args)`
  - requires one of:
    - CLI: `--allow-autocommit`
    - ENV: `TEAMCHAT_ALLOW_AUTOCOMMIT=1`
- Auto-commit now requires **both** user-direction and autocommit opt-in.

## 3) Self-audit payload schema (implemented)
For each auto-commit, `workspace/scripts/team_chat.py` now writes:
- `workspace/audit/teamchat_autocommit_<timestamp>.md`

Required headings/fields generated:
- `## Required Fields`
  - `commit_sha`
  - `actor_mode`
  - `rationale`
- `## Files Changed (name-status)`
- `## Commands Run + Outcomes`
- `## Cleanliness Evidence (git status)`
- `## Reproducibility`

## 4) Evidence runs

### 4.1 Default path (no opt-in) does not commit
Clean worktree verification at `/tmp/wt_autocommit_verify`:

```bash
git worktree add -f /tmp/wt_autocommit_verify HEAD
cd /tmp/wt_autocommit_verify
git status --porcelain -uall
git rev-parse --short HEAD
bash workspace/scripts/verify_team_chat.sh
```

Observed:
- `before=f6fe829 after=f6fe829`
- `git status --porcelain -uall` remained empty
- No new commit created

### 4.2 Opt-in path commits and includes audit artifact

```bash
cd /tmp/wt_autocommit_verify
printf "autocommit probe\n" > workspace/audit/autocommit_probe_marker.txt
TEAMCHAT_USER_DIRECTED_TEAMCHAT=1 TEAMCHAT_ALLOW_AUTOCOMMIT=1 bash workspace/scripts/verify_team_chat.sh
git show --name-status --oneline HEAD
```

Observed:
- `before=f6fe829 after=81cec9a`
- `new_commits=1`
- Commit includes:
  - `A workspace/audit/autocommit_probe_marker.txt`
  - `A workspace/audit/teamchat_autocommit_20260220T084305Z.md`

## 5) Audit of concrete commit `5efdb53`
Evidence commands:
```bash
git show --stat --oneline 5efdb53
git show --name-status --oneline 5efdb53
git show 5efdb53:workspace/audit/evolution_ideas_1_10_20260220T063914Z.md
```

Assessment:
- Opt-in recorded: **No** (old code path had no gating).
- Self-audit payload: **No dedicated autocommit self-audit artifact**.
- Content scope: docs-only (`README.md`, evolution audit file), no stealth code injection.
- Reproducibility/provenance: partial (commit message present, but lacks autocommit contract metadata).

Remediation decision:
- No history rewrite.
- Governance guardrail added prospectively.
- This audit records retroactive compliance assessment for `5efdb53`.

## 6) Enforcement tests added
- `tests_unittest/test_team_chat_autocommit_contract.py`
  - `test_default_signals_are_off`
  - `test_env_signals_are_recognized`
  - `test_no_opt_in_creates_no_commit`
  - `test_opt_in_creates_commit_and_audit_artifact`

## 7) Commands + outcomes
```bash
python3 -m unittest -q tests_unittest/test_team_chat_autocommit_contract.py
```
- Outcome: `Ran 4 tests ... OK`

(Full suite outcomes captured in branch validation step below.)

## 8) Reproducibility
- Default non-commit:
  - `bash workspace/scripts/verify_team_chat.sh`
- Opt-in commit:
  - `TEAMCHAT_USER_DIRECTED_TEAMCHAT=1 TEAMCHAT_ALLOW_AUTOCOMMIT=1 bash workspace/scripts/verify_team_chat.sh`
- Review latest auto-commit audit:
  - `ls workspace/audit/teamchat_autocommit_*.md`
  - `git show --name-status --oneline HEAD`

## 9) Full regression gates
```bash
python3 -m unittest -q
npm test --silent
python3 workspace/scripts/verify_goal_identity_invariants.py
bash workspace/scripts/verify_team_chat.sh
```

Outcomes:
- `python3 -m unittest -q` => `Ran 143 tests ... OK`
- `npm test --silent` => `OK 38 test group(s)`
- `python3 workspace/scripts/verify_goal_identity_invariants.py` => exit `0`
- `bash workspace/scripts/verify_team_chat.sh` => `ok` and no branch commit side effect

## 10) Compliance conclusion
- Prior commit `5efdb53` was **non-compliant** with explicit opt-in and dedicated self-audit contract.
- Current implementation is **opt-in gated** and emits a structured self-audit artifact on autocommit.
- Enforcement tests now fail closed for no-opt-in commit creation and require audit artifact generation on opt-in.
