#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jeebs/src/clawd"
ENGINE_ROOT="${DALI_FISHTANK_UE5_ENGINE_ROOT:-$ROOT/.runtime/UnrealEngine-5.6}"
EDITOR_BIN="${DALI_FISHTANK_UE5_EDITOR_BIN:-$ENGINE_ROOT/Engine/Binaries/Linux/UnrealEditor}"
PROJECT="${DALI_FISHTANK_UE5_PROJECT:-$ROOT/workspace/dali_unreal/DaliMirror.uproject}"
LOCAL_GAME_BIN="$ROOT/workspace/dali_unreal/Binaries/Linux/DaliMirror"
STAGED_GAME_LAUNCHER="$ROOT/workspace/dali_unreal/Saved/StagedBuilds/Linux/DaliMirror.sh"
MAP_PATH="${DALI_FISHTANK_UE5_MAP:-/Engine/Maps/Entry}"
MODE="${DALI_FISHTANK_UE5_MODE:-idle_replay}"
PREFER_LOCAL="${DALI_FISHTANK_UE5_PREFER_LOCAL_BINARY:-0}"

resolve_launcher() {
  if [[ "$PREFER_LOCAL" == "1" ]]; then
    if [[ -x "$LOCAL_GAME_BIN" ]]; then
      printf 'local\n%s\n' "$LOCAL_GAME_BIN"
      return 0
    fi
    if [[ -x "$STAGED_GAME_LAUNCHER" ]]; then
      printf 'staged\n%s\n' "$STAGED_GAME_LAUNCHER"
      return 0
    fi
  fi

  if [[ -x "$STAGED_GAME_LAUNCHER" ]]; then
    printf 'staged\n%s\n' "$STAGED_GAME_LAUNCHER"
    return 0
  fi
  if [[ -x "$LOCAL_GAME_BIN" ]]; then
    printf 'local\n%s\n' "$LOCAL_GAME_BIN"
    return 0
  fi
  if [[ -x "$EDITOR_BIN" ]]; then
    printf 'editor\n%s\n' "$EDITOR_BIN"
    return 0
  fi
  return 1
}

if [[ ! -f "$PROJECT" ]]; then
  echo "UE project missing: $PROJECT" >&2
  exit 1
fi

if ! RESOLVED="$(resolve_launcher)"; then
  echo "No UE launcher available." >&2
  echo "Expected one of:" >&2
  echo "  $EDITOR_BIN" >&2
  echo "  $STAGED_GAME_LAUNCHER" >&2
  echo "  $LOCAL_GAME_BIN" >&2
  exit 1
fi

LAUNCHER_KIND="$(printf '%s\n' "$RESOLVED" | sed -n '1p')"
LAUNCHER="$(printf '%s\n' "$RESOLVED" | sed -n '2p')"

ARGS=()
if [[ "$LAUNCHER_KIND" == "editor" ]]; then
  ARGS+=("$PROJECT")
  ARGS+=("$MAP_PATH")
  ARGS+=("-game")
elif [[ "$LAUNCHER_KIND" == "local" ]]; then
  ARGS+=("$PROJECT")
  ARGS+=("$MAP_PATH")
else
  ARGS+=("$MAP_PATH")
fi

ARGS+=("-NoSplash")
ARGS+=("-NoLoadingScreen")
ARGS+=("-ResX=${DALI_FISHTANK_UE5_RESX:-3840}")
ARGS+=("-ResY=${DALI_FISHTANK_UE5_RESY:-2160}")

case "$MODE" in
  idle_replay)
    ARGS+=("-CMIdleReplayAutostart")
    ;;
  fantasy_landscape)
    ARGS+=("-CMFantasyLandscapeAutostart")
    ;;
  fantasy_landscape_v2)
    ARGS+=("-CMFantasyLandscapeV2Autostart")
    ;;
esac

if [[ "${DALI_FISHTANK_FULLSCREEN:-1}" == "0" ]]; then
  ARGS+=("-windowed")
else
  ARGS+=("-fullscreen")
fi

if [[ -n "${DALI_FISHTANK_UE5_CAPTURE_FILE:-}" ]]; then
  ARGS+=("-DaliCapturePath=${DALI_FISHTANK_UE5_CAPTURE_FILE}")
  ARGS+=("-DaliCaptureDelay=${DALI_FISHTANK_UE5_CAPTURE_DELAY:-4}")
  ARGS+=("-DaliExitDelay=${DALI_FISHTANK_UE5_EXIT_DELAY:-4}")
fi

if [[ -n "${DALI_FISHTANK_UE5_EXTRA_ARGS:-}" ]]; then
  # Intentionally split on shell words so operators can pass multiple engine args.
  # shellcheck disable=SC2206
  EXTRA_ARGS=( ${DALI_FISHTANK_UE5_EXTRA_ARGS} )
  ARGS+=("${EXTRA_ARGS[@]}")
fi

exec "$LAUNCHER" "${ARGS[@]}" "$@"
