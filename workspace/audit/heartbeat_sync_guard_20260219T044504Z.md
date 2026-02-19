# HEARTBEAT Sync Guard Evidence (20260219T044504Z)

## Scope
- Add a mechanical sync+assert guard for HEARTBEAT mirror drift.
- Canonical: `workspace/governance/HEARTBEAT.md`
- Mirror: `HEARTBEAT.md` (tracked, byte-identical)

## Commands Run
1. `npm run -s governance:heartbeat`
   - Result: `heartbeat sync guard: ok canonical=/Users/heathyeager/clawd/workspace/governance/HEARTBEAT.md mirror=/Users/heathyeager/clawd/HEARTBEAT.md`
2. `npm test`
   - Result: PASS (`Ran 94 tests ... OK`, `OK 35 test group(s)`).
3. `bash workspace/scripts/verify_tacti_system.sh`
   - Result: PASS (`Ran 16 tests ... OK`, artifact written).

## Files Changed (governance drift prevention)
- `workspace/scripts/sync_heartbeat.sh` (new)
- `workspace/scripts/verify_goal_identity_invariants.py`
- `package.json`

## Notes
- Verifier now invokes `sync_heartbeat.sh` when present, preserving fixture-based tests where the script is intentionally absent.
