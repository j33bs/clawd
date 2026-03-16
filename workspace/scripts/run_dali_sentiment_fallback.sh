#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

exec /usr/bin/env python3 "$ROOT_DIR/workspace/scripts/dali_sentiment_fallback.py" "$@"
