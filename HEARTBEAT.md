# HEARTBEAT.md

# OpenClaw heartbeat runner reads this file and executes these checks.
# Every task includes cadence, command, output artifact, and failure signal.

- [HB-01] Daily Briefing Health
  cadence: daily@07:00 Australia/Brisbane
  cmd: `python3 workspace/scripts/automation_status.py cron-health --job-name "Daily Morning Briefing" --max-age-hours 26 --artifact reports/automation/briefing_health.json`
  artifact: `reports/automation/briefing_health.json`
  fail: command exits non-zero OR artifact `pass=false`.

- [HB-02] HiveMind Ingest Health
  cadence: daily@07:30 Australia/Brisbane
  cmd: `python3 workspace/scripts/automation_status.py cron-health --job-name "HiveMind Ingest" --max-age-hours 26 --artifact reports/automation/hivemind_ingest_health.json`
  artifact: `reports/automation/hivemind_ingest_health.json`
  fail: command exits non-zero OR artifact `pass=false`.

- [HB-03] MEMORY.md Size Guard
  cadence: nightly
  cmd: `python3 workspace/scripts/automation_status.py memory-size-guard --memory-file MEMORY.md --threshold-lines 180 --artifact reports/memory/memory_size_guard.json`
  artifact: `reports/memory/memory_size_guard.json`
  fail: artifact `needs_prune=true`.

- [HB-04] Contradiction/Integrity Quick Scan
  cadence: nightly
  cmd: `python3 workspace/scripts/automation_status.py integrity-scan --artifact reports/memory/integrity_scan.json`
  artifact: `reports/memory/integrity_scan.json`
  fail: command exits non-zero OR artifact `pass=false`.

- [HB-05] Local Inference Probe Summary
  cadence: every 6h
  cmd: `mkdir -p reports/health && node scripts/vllm_probe.js --json > reports/health/vllm_status.json`
  artifact: `reports/health/vllm_status.json`
  fail: command exits non-zero.

- [HB-06] Nightly Research Ingest
  cadence: nightly
  cmd: `bash workspace/scripts/nightly_build.sh research`
  artifact: `reports/research/ingest_status.json`
  fail: command exits non-zero OR artifact missing.
