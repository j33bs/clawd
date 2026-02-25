# C_Lawd Dashboard Reachability + Pause/Researcher Implementation Audit

## Summary
Implemented and validated:
1. Dashboard reachability recovery on macOS when gateway service state is confusing/non-listening.
2. Pause gate remains opt-in (`OPENCLAW_PAUSE_CHECK=1`) with deterministic tests.
3. Researcher novelty/duplicate logic is now opt-in (`OPENCLAW_WANDERER_RESEARCHER=1`) and off by default.

## Dashboard Root Cause + Evidence
Root cause observed in this session:
- No listener on `127.0.0.1:18789` (`ECONNREFUSED` from `curl`, empty `lsof` listener output).
- `openclaw gateway status` showed service state transitions that were misleading/non-actionable while the port was not listening.
- Manual launchctl recovery (`kickstart`) restored listener and dashboard.

Evidence highlights:
- Before recovery: `curl http://127.0.0.1:18789/` => connection refused.
- After recovery: `lsof` showed node listening on both `127.0.0.1:18789` and `[::1]:18789`.
- After recovery: `curl` returned `HTTP/1.1 200 OK` for:
  - `http://127.0.0.1:18789/`
  - `http://localhost:18789/`
  - `http://[::1]:18789/`

## Fixes Applied
### Gateway diagnostics
- Hardened `workspace/scripts/diagnose_openclaw_status_hang.py` to detect:
  - launch agent loaded but gateway port not listening
  - explicit `gateway.mode=local` startup block condition
- Added unit tests for these detection paths.

### Pause feature
- Existing pause gate wiring verified at pre-response stage in `workspace/scripts/team_chat_adapters.py`.
- Pause event log path now writes to:
  - `workspace/state/pause_check_events.jsonl`

### Researcher feature
- `workspace/scripts/research_wanderer.py` now gates novelty/duplicate behavior behind:
  - `OPENCLAW_WANDERER_RESEARCHER=1`
- Default (`flag off`) preserves legacy wander behavior.
- Flag-on behavior keeps deterministic offline novelty suppression and now logs `attempts` in table rows.

## Feature Flags
- Pause gate: `OPENCLAW_PAUSE_CHECK=1`
- Pause deterministic test path: `OPENCLAW_PAUSE_CHECK_TEST_MODE=1`
- Researcher novelty/duplicate path: `OPENCLAW_WANDERER_RESEARCHER=1`

## Commands Run (Key)
### Diagnostics / recovery
- `openclaw status`
- `openclaw health`
- `openclaw gateway status`
- `lsof -nP -iTCP:18789 -sTCP:LISTEN`
- `curl -v http://127.0.0.1:18789/`
- `curl -v http://localhost:18789/`
- `curl -v http://[::1]:18789/`
- `openclaw gateway install`
- `launchctl kickstart -k gui/$UID/ai.openclaw.gateway`

### Tests
- `python3 -m unittest tests_unittest/test_pause_check.py tests_unittest/test_team_chat_pause_gate.py tests_unittest/test_research_wanderer_novelty.py tests_unittest/test_diagnose_openclaw_status_hang.py`

Expected summary:
- All tests pass.

## Rollback
1. Revert commit(s):
   - `git revert <sha>`
2. Manual file rollback (if needed):
   - `workspace/scripts/research_wanderer.py`
   - `workspace/scripts/team_chat_adapters.py`
   - `workspace/scripts/diagnose_openclaw_status_hang.py`
   - `tests_unittest/test_research_wanderer_novelty.py`
   - `tests_unittest/test_diagnose_openclaw_status_hang.py`
3. Dashboard runtime rollback (if needed):
   - `openclaw gateway stop`
   - `launchctl bootout gui/$UID/ai.openclaw.gateway`
