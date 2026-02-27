# /api/procs compatibility decision
timestamp_utc: 20260227T094134Z

inputs:
- consumer_scan: /tmp/api_procs_consumers_20260227T094134Z.txt
- live_headers: /tmp/api_procs_headers_20260227T094134Z.txt

observations:
- in-repo consumers found: 0
- live /api/procs on main: returned HTML shell surface (not a known machine consumer signal)

decision:
- do not merge compat alias; keep machine surface minimal
- reverted branch commit on codex/fix/dashboard-procs-20260227T083957Z via cec2b41
- no open PR existed for that branch to close
