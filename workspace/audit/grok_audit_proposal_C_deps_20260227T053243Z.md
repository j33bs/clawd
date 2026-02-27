# Proposal C — Centralise Python deps

timestamp_utc: 20260227T053243Z
Intent: Reproducible builds; reduce hidden state.
Scope: workspace/requirements.txt (external deps only; minimal set from repo imports).
Verification: file exists and non-empty.
Notes: tools/regression.sh not present in this repo root; no regression hook insertion was applied.
