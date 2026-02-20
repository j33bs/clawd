Title:
feat(evolution): implement ideas 1–10 (flag-gated)

Body:
## 1) Summary
- Implements evolution ideas 1–10 as deterministic, flag-gated increments with defaults OFF.
- Preserves existing routing/memory/audit contracts and adds compatibility aliases for prior flag names.
- Adds/extends deterministic tests for each subsystem contract (dream pruning, router proprioception arousal input, trails valence, temporal surprise gate, peer annealing, narrative distill idempotency, active inference counterfactual replay, semantic immune epitopes, oscillatory attention gating, witness tamper detection).
- Deferrals: none required for this slice.

## 2) Governance hardening
- TeamChat autocommit now requires dual opt-in:
  - user direction signal: `--user-directed-teamchat` or `TEAMCHAT_USER_DIRECTED_TEAMCHAT=1`
  - autocommit opt-in: `--allow-autocommit` or `TEAMCHAT_ALLOW_AUTOCOMMIT=1`
- On opt-in commit, TeamChat now emits a self-audit artifact:
  - `workspace/audit/teamchat_autocommit_<timestamp>.md`
- Added enforcement tests for no-opt-in/no-commit and opt-in/commit+audit behavior.

## 3) Flags
- `OPENCLAW_DREAM_PRUNING=0`
- `OPENCLAW_ROUTER_PROPRIOCEPTION=0`
- `OPENCLAW_TRAILS_VALENCE=0`
- `OPENCLAW_TEMPORAL_SURPRISE_GATE=0`
- `OPENCLAW_PEERGRAPH_ANNEAL=0`
- `OPENCLAW_NARRATIVE_DISTILL=0`
- `OPENCLAW_AIF_COUNTERFACTUAL=0`
- `OPENCLAW_SEMANTIC_IMMUNE_EPITOPES=0`
- `OPENCLAW_OSCILLATORY_ATTENTION=0`
- `OPENCLAW_WITNESS_LEDGER=0`
- Compatibility aliases retained: `OPENCLAW_DREAM_PRUNE`, `OPENCLAW_TRAIL_VALENCE`, `OPENCLAW_SURPRISE_GATE`, `OPENCLAW_PEER_ANNEAL`, `OPENCLAW_COUNTERFACTUAL_REPLAY`, `OPENCLAW_EPITOPE_CACHE`, `OPENCLAW_OSCILLATORY_GATING`.

## 4) Evidence
- `workspace/audit/evolution_ideas_1_10_*.md`
- `workspace/audit/evolution_ideas_1_10_20260220T063914Z.md`
- `workspace/audit/audit_autocommit_contract_20260220T084401Z.md`

## 5) Verification commands
- `python3 -m unittest -q`
- `npm test --silent`
- `bash workspace/scripts/verify_team_chat.sh` (default: no commit)
- `TEAMCHAT_USER_DIRECTED_TEAMCHAT=1 TEAMCHAT_ALLOW_AUTOCOMMIT=1 bash workspace/scripts/verify_team_chat.sh` (opt-in: commit + audit artifact)

## 6) Rollback guidance
- `git revert <merge-commit-sha>` (fill after merge)
