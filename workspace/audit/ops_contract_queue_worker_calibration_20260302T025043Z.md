# Ops: Contract + Queue + Heavy Worker + Calibration (REAL) — 20260302T025043Z

## Context
This note continues from prior evidence bundle:
- workspace/audit/_evidence/contract_queue_calibrate_20260302T022709Z

Host runtime change (already applied previously):
- openclaw-heavy-worker.timer installed/enabled on Dali (systemd user)

Rollback (host):
- systemctl --user disable --now openclaw-heavy-worker.timer
- rm -f ~/.config/systemd/user/openclaw-heavy-worker.{service,timer}
- systemctl --user daemon-reload

## This run
- Commits the existing contract/queue/worker tranche.
- Adds heavy GPU job lifecycle ownership via ensure_coder_vllm_up.
- Adds queue_depth backlog-pressure bias in contract mode selection.
- Captures a real calibration run (15m active + 10m idle) and recommended thresholds artifact.

## Evidence
- workspace/audit/_evidence/commit_calibrate_worker_20260302T025043Z

## Calibration (REAL) — 20260302T025043Z
- Evidence bundle: workspace/audit/_evidence/commit_calibrate_worker_20260302T025043Z
- Outputs:
  - workspace/audit/_evidence/commit_calibrate_worker_20260302T025043Z/calibration_report_real.json
  - workspace/audit/_evidence/commit_calibrate_worker_20260302T025043Z/recommended_thresholds_real.json
  - workspace/audit/_evidence/commit_calibrate_worker_20260302T025043Z/calibration_summary_real.txt

Recommendation snapshot:
- service_rate_high: 3.544
- service_rate_low: 2.625
- idle_window_seconds: 480

Policy:
- Recommendation captured only; high/low defaults were not auto-applied in this run.
