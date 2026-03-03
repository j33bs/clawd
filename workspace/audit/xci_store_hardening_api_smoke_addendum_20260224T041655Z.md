# XCI API Smoke Addendum

- Timestamp (UTC): 2026-02-24T04:16:55Z
- Branch: `claude-code/governance-session-20260223`
- HEAD SHA: `732a8f03d1a6ac485b3e2b3d7df02fba88a1cca3`

## API start command

```bash
source workspace/venv/bin/activate
python3 -m uvicorn workspace.store.api:app --host 127.0.0.1 --port 18790
```

## Curl checks executed

```bash
curl -s "http://127.0.0.1:18790/status"
curl -s "http://127.0.0.1:18790/tail?n=50"
curl -s "http://127.0.0.1:18790/tail?n=200&retro_dark=true"
curl -s "http://127.0.0.1:18790/tail?n=200&retro_dark=false"
```

### /status output

```json
{"status":"live","section_count":92,"store_rows":92,"model":"all-MiniLM-L6-v2","uptime_seconds":0.1,"timestamp":"2026-02-24T04:16:21.821959Z","exec_tags":["EXEC:HUMAN_OK"],"rule_store_001":"linear_tail is the default; semantic search is opt-in (factual queries only)","rule_store_002":"exec_tags/status_tags never encoded in vectors; metadata predicates only"}
```

### /tail output summary

- `/tail?n=50`: 50 rows returned (baseline, unfiltered)
- `/tail?n=200&retro_dark=true`: 92 rows returned
- `/tail?n=200&retro_dark=false`: 0 rows returned
- Validation checks:
  - `status_exec_tags_ok`: `True` (`["EXEC:HUMAN_OK"]` present)
  - `retro_dark_true_only_nonempty`: `True`
  - `retro_dark_false_only_empty`: `True`

Notes:
- This dataset currently has no sections with empty `retro_dark_fields`, so `retro_dark=false` correctly returns an empty set.
- No code changes were required for API behavior.

## Result

API smoke passed.
