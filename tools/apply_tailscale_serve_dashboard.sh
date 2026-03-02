#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "$REPO_ROOT" ]; then
  "$REPO_ROOT/tools/guard_worktree_boundary.sh"
fi

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo" >&2
  exit 1
fi

if ! command -v tailscale >/dev/null 2>&1; then
  echo "FAIL: tailscale not installed (tailscale binary missing)" >&2
  exit 1
fi

tailscale serve reset || true
pkill -f "tailscale serve" || true
tailscale serve --bg 18789
tailscale serve status
