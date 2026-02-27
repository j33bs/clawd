#!/usr/bin/env bash
set -euo pipefail

echo "=== OpenClaw Tailscale Peers ==="
tailscale status | awk '{print $1,$2,$4}' | grep -v offline || true
