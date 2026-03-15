#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jeebs/src/clawd"

cat <<EOF
Phase One canonical docs:
- $ROOT/workspace/dali_unreal/Docs/PhaseOneOfflinePipeline.md
- $ROOT/workspace/handoffs/dali_phase1_offline_pipeline_2026-03-09.md

UE5 scaffold roots:
- $ROOT/workspace/dali_unreal/DaliMirror.uproject
- $ROOT/workspace/dali_unreal/Source/DaliMirror
- $ROOT/workspace/dali_unreal/Config/DefaultEngine.ini

Runtime/control plane kept for later:
- $ROOT/workspace/cathedral/runtime.py
- $ROOT/workspace/cathedral/control_api.py
- $ROOT/scripts/dali_fishtank_start.sh

Historical context:
- $ROOT/workspace/audit/cathedral_ue5_handoff_20260308T123354Z.md
- $ROOT/memory/2026-03-08.md
- $ROOT/memory/2026-03-09.md
EOF
