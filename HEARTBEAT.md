# HEARTBEAT.md
# Canonical path: workspace/governance/HEARTBEAT.md
# Repo-root HEARTBEAT.md must remain byte-identical with this file.
# Agents should add or edit heartbeat tasks here, then sync the repo-root mirror.

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.

- [HB-PR-01] MEMORY size guard
  - Check `wc -l /Users/heathyeager/clawd/MEMORY.md`; warn if `> 180`.

- [HB-PR-02] Nightly log health
  - Check `reports/nightly/$(date +%Y-%m-%d).log` exists and scan for `⚠️`.

- [HB-PR-03] QMD MCP daemon health
  - Check daemon responsiveness on port `8181` (for example `curl -fsS http://127.0.0.1:8181/`).

- [HB-PR-04] KB sync freshness reminder
  - Compare latest workspace markdown mtime vs `workspace/knowledge_base/data/last_sync.txt`.
  - If workspace files are newer, remind to run `python3 workspace/knowledge_base/kb.py sync`.

- [HB-PR-05] Repeated request inefficiency capture
  - If Heath repeats the same request 3+ times in a session, append an entry to `workspace/governance/inefficiency_log.md`.

- [HB-PR-06] System Consciousness (Φ) Alignment Measure
  - Check AIN agent status: `curl -fsS http://127.0.0.1:18990/api/ain/phi`
  - If running, log Φ value to track alignment over time
  - This measures system integration/coherence from AIN research
