#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_PLIST="$ROOT_DIR/workspace/launchd/ai.openclaw.ain.plist"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST_PLIST="$DEST_DIR/ai.openclaw.ain.plist"
UID_NUM="$(id -u)"
LABEL="ai.openclaw.ain"

if [ ! -f "$SRC_PLIST" ]; then
  echo "FAIL: missing plist at $SRC_PLIST" >&2
  exit 1
fi

mkdir -p "$DEST_DIR" "$ROOT_DIR/workspace/runtime/logs"
cp "$SRC_PLIST" "$DEST_PLIST"

launchctl bootout "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID_NUM" "$DEST_PLIST"
launchctl enable "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 || true

echo "Installed: $DEST_PLIST"
launchctl print "gui/$UID_NUM/$LABEL" | sed -n '1,80p'
echo "Rollback:"
echo "  launchctl bootout gui/$UID_NUM/$LABEL"
echo "  rm -f $DEST_PLIST"
