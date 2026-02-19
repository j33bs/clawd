# System Stability Bundle

Start SHA: c6a489a

## Change 1: Nightly build cron stability
- Updated `workspace/scripts/nightly_build.sh` to resolve `openclaw` via PATH fallback and fixed archive counting without subshell counter loss.
- Command: `bash workspace/scripts/nightly_build.sh health`
- Exit: `0`
- Log path: `reports/nightly/2026-02-19.log`
- Evidence: health step completed and log updated.

## Change 2: MEMORY.md line count guard
- Added warning in `run_memory()` when `MEMORY.md` line count exceeds threshold (default 180; local test override via `NIGHTLY_MEMORY_WARN_LINES`).
- Command: `NIGHTLY_MEMORY_WARN_LINES=50 bash workspace/scripts/nightly_build.sh memory`
- Exit: `0`
- Evidence line: `⚠️ MEMORY.md exceeds 180 lines — prune recommended (oldest entries first)` in `reports/nightly/2026-02-19.log`.

## Change 3: KB sync path/content + nightly wire
- Fixed KB graph subprocess path typo (`knowledge-base` -> `knowledge_base`).
- Updated `kb.py cmd_sync()` to extract entities from document content (first 500 chars), including QMD virtual paths via `qmd get`.
- Added nightly `run_kb_sync()` step in `workspace/scripts/nightly_build.sh` (warn-only on failure).
- Commands:
  - `python3 workspace/knowledge_base/kb.py sync` -> `✅ Synced 10 documents to knowledge graph`
  - `python3 workspace/knowledge_base/kb.py stats` -> entities now `32`.

## Change 4: KB decision provenance
- Added `workspace/scripts/extract_decisions.py` to index decision-like commit messages (`feat/fix/harden/sec/const`) into KB with `entity_type=decision` and `source=git:<sha>`.
- Wired nightly `run_kb_decisions()` step (warn-only) in `workspace/scripts/nightly_build.sh`.
- Commands:
  - `python3 workspace/scripts/extract_decisions.py` -> `Decisions indexed: 24`
  - Decision entity count check -> `decision_entities=25`
  - `python3 workspace/knowledge_base/kb.py query "why did we" --agent main` executed (no relevant answer returned, but decision indexing present in store).

## Change 5: HEARTBEAT proactive tasks
- Added proactive tasks to canonical `workspace/governance/HEARTBEAT.md`:
  - MEMORY line-count warning check (>180)
  - nightly log exists + warning scan
  - QMD MCP port 8181 responsiveness
  - KB sync freshness reminder using `workspace/knowledge_base/data/last_sync.txt`
- Synced canonical -> repo-root mirror with guard:
  - `npm run -s governance:heartbeat`
  - Output: `heartbeat sync guard: ok canonical=... mirror=...`
- No dedicated manual heartbeat tick command found in repo; tasks will execute on next heartbeat cycle.

## Change 6: Daily technique injection into briefing
- Added `daily_technique` exec tool in `openclaw.json` (`python3 scripts/daily_technique.py --format briefing`).
- Added `--format briefing` support in `scripts/daily_technique.py`.
- Updated Daily Morning Briefing payload command in `workspace/automation/cron_jobs.json` to start with technique and include a behavioral prime paragraph.
- Verification:
  - `bash scripts/run_job_now.sh briefing` -> success (`{"ok": true, "ran": true}`)
  - `openclaw cron runs --id <briefing_job_id> --limit 1 --json` summary includes technique + behavioral prime steps.

## Change 7: Daily quote before technique
- Updated Daily Morning Briefing ordering in `workspace/automation/cron_jobs.json` to `quote -> technique -> behavioral prime -> calendar/reminders/news`.
- Added tracked tool metadata (`daily_quote`, `daily_technique`) in template file.
- Verification:
  - `bash scripts/run_job_now.sh briefing` -> success (`{"ok": true, "ran": true}`)
  - `reports/automation/job_status/briefing.json` summary shows quote as step 1 and technique as step 2.

## Change 8: smart_calendar wrapper
- Added `workspace/scripts/smart_calendar.sh`.
- Behavior:
  - Calls `workspace/scripts/calendar.sh today`.
  - Reads low-energy window from `workspace/time_management/data/preferences.json` with fallback to `afternoon`.
  - Annotates matching time lines with `⚠️ [low-energy window]` when calendar output is available.
  - Propagates calendar script failures with explicit error.
- Verification:
  - Command: `bash workspace/scripts/smart_calendar.sh`
  - Result on this host: `smart_calendar: calendar.sh failed` / `error: No calendars.` (expected fail-propagation behavior).

## Change 9: Weekly session pattern analysis cron
- Added weekly cron template job `Session Pattern Analysis` (`0 9 * * 5`, `Australia/Brisbane`) in `workspace/automation/cron_jobs.json`.
- Added `--output` support to `scripts/analyze_session_patterns.js`.
- Verification:
  - `node scripts/analyze_session_patterns.js --output reports/health/session-patterns-latest.md`
  - `openclaw cron run <session-pattern-analysis-job-id> --timeout 120000` -> `{"ok": true, "ran": true}`
  - Report written: `reports/health/session-patterns-latest.md` (heading `# Session Pattern Report`).

## Change 10: Inefficiency log + nightly surfacing
- Added `workspace/governance/inefficiency_log.md` (append-only table format).
- Added HEARTBEAT task (`HB-PR-05`) to append inefficiency entries when a request repeats 3+ times/session.
- Added nightly stale-open surfacing in `run_memory()` (`workspace/scripts/nightly_build.sh`) for open entries older than 7 days.
- Verification:
  - Added temporary test row with old date + `open`, ran `bash workspace/scripts/nightly_build.sh memory`.
  - Log evidence:
    - `⚠️ Inefficiency log has stale open entries (>7 days):`
    - `2026-02-01: TEST-STale repeated request`
  - Removed temporary test row before commit.
- HEARTBEAT mirror sync:
  - `npm run -s governance:heartbeat` -> sync guard OK.


## Gate Fix: cron template test drift (2026-02-19T16:44:32Z)

- Pre-fix SHA: `23c2285`
- Post-fix SHA: `db4dd37`
- Failing gate summary:
  - `python3 -m unittest -v tests_unittest/test_ensure_cron_jobs.py`
  - Failures were hard-coded counts (`len(templates)==2`, two create/unchanged actions) after adding third template job `Session Pattern Analysis`.
- Fix applied:
  - Updated `/Users/heathyeager/clawd/tests_unittest/test_ensure_cron_jobs.py` to assert required job names and schedule invariants, and to compute expected action counts from template length.

### Commands + outcomes

- `python3 -m unittest -v tests_unittest/test_ensure_cron_jobs.py` -> PASS (3 tests)
- `npm test` -> PASS (96 python tests + node test groups)
- `bash workspace/scripts/verify_tacti_system.sh` -> PASS
- `bash workspace/scripts/nightly_build.sh health` -> PASS (exit 0)
- `bash workspace/scripts/nightly_build.sh memory` -> PASS (exit 0)
- `python3 workspace/knowledge_base/kb.py sync` -> PASS (`Synced 10 documents`)
- `python3 workspace/scripts/extract_decisions.py` -> PASS (`Decisions indexed: 24`)
- `npm run -s governance:heartbeat` -> PASS (canonical/mirror sync guard OK)
