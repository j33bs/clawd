#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

python3 "$REPO_ROOT/workspace/teamchat/witness_verify.py" --repo-root "$REPO_ROOT" "$@"
