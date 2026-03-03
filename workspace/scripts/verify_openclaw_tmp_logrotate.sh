#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cfg="$repo_root/workspace/config/logrotate/openclaw-tmp.conf"

if [[ ! -f "$cfg" ]]; then
  echo "FAIL: missing config $cfg"
  exit 1
fi

logrotate_bin="${LOGROTATE_BIN:-$(command -v logrotate || true)}"
if [[ -z "$logrotate_bin" ]]; then
  echo "SKIP: logrotate not found on PATH"
  exit 0
fi

tmp_state="$(mktemp)"
trap 'rm -f "$tmp_state"' EXIT

mkdir -p /tmp/openclaw
touch /tmp/openclaw/openclaw-verify.log /tmp/openclaw/openclaw-verify.jsonl

"$logrotate_bin" -d -s "$tmp_state" "$cfg" >/dev/null
echo "PASS: openclaw tmp logrotate dry-run"
