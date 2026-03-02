#!/usr/bin/env bash
set -euo pipefail

SOURCE_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "${SOURCE_PATH}")" && pwd)"
REPO_ROOT="${OPENCLAW_HOME:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
LABEL="${OPENCLAW_TAILSCALE_SERVE_LABEL:-ai.openclaw.tailscale-serve}"
PLIST_PATH="${OPENCLAW_TAILSCALE_SERVE_PLIST_PATH:-$HOME/Library/LaunchAgents/${LABEL}.plist}"
SERVE_SCRIPT="${OPENCLAW_TAILSCALE_SERVE_SCRIPT:-${REPO_ROOT}/scripts/tailscale_serve_openclaw.sh}"
WORKDIR="${OPENCLAW_TAILSCALE_SERVE_WORKDIR:-${REPO_ROOT}}"
LOG_DIR="${OPENCLAW_TAILSCALE_SERVE_LOG_DIR:-$HOME/Library/Logs}"
APPLY="${OPENCLAW_TAILSCALE_SERVE_LAUNCHCTL_APPLY:-0}"
DRYRUN="${OPENCLAW_TAILSCALE_SERVE_LAUNCHAGENT_DRYRUN:-0}"

if [[ ! -f "$SERVE_SCRIPT" ]]; then
  echo "FATAL: serve script missing: $SERVE_SCRIPT" >&2
  exit 2
fi

emit_plist() {
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>${SERVE_SCRIPT}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${WORKDIR}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/${LABEL}.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/${LABEL}.err.log</string>
</dict>
</plist>
EOF
}

if [[ "$DRYRUN" == "1" ]]; then
  echo "PLIST_PATH=${PLIST_PATH}"
  emit_plist
  exit 0
fi

mkdir -p "$(dirname "$PLIST_PATH")" "$LOG_DIR"
tmp_plist="$(mktemp "${TMPDIR:-/tmp}/${LABEL}.XXXXXX")"
trap 'rm -f "$tmp_plist"' EXIT INT TERM
emit_plist >"$tmp_plist"
chmod 600 "$tmp_plist"
mv "$tmp_plist" "$PLIST_PATH"
trap - EXIT INT TERM

echo "WROTE_PLIST=${PLIST_PATH}"

if [[ "$APPLY" == "1" ]]; then
  uid="$(id -u)"
  launchctl bootout "gui/${uid}/${LABEL}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/${uid}" "$PLIST_PATH"
  launchctl kickstart -k "gui/${uid}/${LABEL}"
  echo "LAUNCHCTL_APPLIED=1"
else
  echo "LAUNCHCTL_APPLIED=0"
fi
