#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

export TEAMCHAT_LIVE=0
export TEAMCHAT_AUTO_COMMIT=0
export TEAMCHAT_ACCEPT_PATCHES=0

export TACTI_CR_ENABLE=1
export TACTI_CR_AROUSAL_OSC=1
export TACTI_CR_DREAM_CONSOLIDATION=1
export TACTI_CR_SEMANTIC_IMMUNE=1
export TACTI_CR_STIGMERGY=1
export TACTI_CR_EXPRESSION_ROUTER=1
export TACTI_CR_PREFETCH=1
export TACTI_CR_MIRROR=1
export TACTI_CR_VALENCE=1
export TACTI_CR_TEMPORAL_WATCHDOG=1
export SOURCE_UI_HEATMAP=1

python3 workspace/scripts/run_novel10_fixture.py \
  --fixtures-dir workspace/fixtures/novel10 \
  --events-path workspace/state/tacti_cr/events.jsonl \
  --now 2026-02-19T13:00:00Z \
  --enable-all \
  --no-ui

python3 workspace/scripts/verify_tacti_cr_novel10_fixture.py \
  --events-path workspace/state/tacti_cr/events.jsonl
