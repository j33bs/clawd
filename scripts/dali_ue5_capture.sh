#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jeebs/src/clawd"
PROJECT="$ROOT/workspace/dali_unreal/DaliMirror.uproject"
GAME_BIN="$ROOT/workspace/dali_unreal/Binaries/Linux/DaliMirror"
OUT_DIR="$ROOT/workspace/audit/_evidence/ue5_capture_$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$OUT_DIR/run.log"
SHOT_DIR="$ROOT/workspace/dali_unreal/Saved/Screenshots"

mkdir -p "$OUT_DIR"
rm -rf "$SHOT_DIR"/Linux* "$SHOT_DIR"/LinuxEditor* || true
mkdir -p "$SHOT_DIR"

if [[ ! -x "$GAME_BIN" ]]; then
  echo "Game binary missing: $GAME_BIN" >&2
  exit 1
fi

set +e
timeout 180s "$GAME_BIN" "$PROJECT" /Engine/Maps/Entry \
  -RenderOffscreen \
  -ResX=1280 \
  -ResY=720 \
  -unattended \
  -nosplash \
  -NoSound \
  -stdout \
  -FullStdOutLogOutput \
  -ExecCmds="HighResShot 1; quit" \
  >"$LOG_FILE" 2>&1
RC=$?
set -e

find "$SHOT_DIR" -type f -print0 | while IFS= read -r -d '' file; do
  cp "$file" "$OUT_DIR"/
done

printf 'exit_code=%s\n' "$RC" | tee "$OUT_DIR/result.txt"
echo "$OUT_DIR"
