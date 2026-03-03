#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

export TEAMCHAT_AUTO_COMMIT=0
export TEAMCHAT_ACCEPT_PATCHES=0
export TEAMCHAT_LIVE=0

python3 workspace/scripts/verify_tacti_cr_events.py "$@"
