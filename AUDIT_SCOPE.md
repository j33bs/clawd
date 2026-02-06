# AUDIT_SCOPE.md — What Changed / What Needs Auditing

Update this file after each admission or before each audit.

## Current State

- **last_admitted_commit**: `fdaee04` (Make Ollama provider optional)
- **branch**: `develop`

## Changed Areas

- Multi-agent wiring (claude-code agent added, delegation protocol)
- Operational infrastructure (cron jobs, heartbeat, memory logging)
- Workspace hygiene (.gitignore, regression script fixes)
- Audit protocol (this file, AUDIT_README.md, AUDIT_SNAPSHOT.md)

## Files Changed

- `.gitignore` — Runtime dir patterns, diagnostic script exclusions
- `openclaw.json` — claude-code agent registered, empty bindings
- `workspace/AGENTS.md` — Multi-agent delegation section, audit pointer
- `workspace/MEMORY.md` — Architecture docs, cron jobs, regression details
- `workspace/MODEL_ROUTING.md` — Decision tree for delegation
- `workspace/scripts/regression.sh` — python3->python fix, numbering fix

## New Files

- `AUDIT_README.md` — Audit protocol constraints and strategy
- `AUDIT_SCOPE.md` — This file
- `AUDIT_SNAPSHOT.md` — Last audit signals
- `README.md` — ITC pipeline project documentation
- `workspace/CLAUDE_CODE.md` — claude-code agent context
- `workspace/HEARTBEAT.md` — Proactive heartbeat checks + cron semantics
- `workspace/TOOLS.md` — Local tools/environment notes
- `workspace/handoffs/.gitkeep` — Handoff directory marker
- `workspace/memory/.gitkeep` — Memory directory marker
- `workspace/sources/itc/*` — 20 governance files (digests, regression datasets, charters)

## Audit Focus

- Verify claude-code delegation wiring (AGENTS.md instructions match sessions_spawn API)
- Verify cron job config matches documented schedule (02:00 UTC = 12:00 AEST)
- Verify .gitignore covers all runtime dirs (no secrets leaking into tracked files)
- Verify regression.sh passes clean (all 8/8 checks)
- Verify handoff protocol files match documented format

## Skip If All Checks Pass

- Constitutional invariants (regression check 1)
- Governance substrate (regression check 2)
- Secret scan (regression check 3)
- Forbidden files (regression check 4)
- Git hooks (regression check 5)
- Documentation completeness (regression check 6)

## Suggested Commands

```bash
cd C:\Users\heath\.openclaw
git diff --name-status               # What changed
bash workspace/scripts/regression.sh # 8-check regression
bash workspace/scripts/verify.sh     # Full pre-admission verification
git status                           # Untracked/modified overview
openclaw cron list                   # Cron job state
```
