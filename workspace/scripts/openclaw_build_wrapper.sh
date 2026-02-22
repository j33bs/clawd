#!/usr/bin/env bash
set -euo pipefail

# OPENCLAW_BUILD_STAMP_WRAPPER=1
REAL_BIN="${OPENCLAW_REAL_BIN:-$HOME/.local/bin/openclaw.real}"
STAMP_FILE="${OPENCLAW_BUILD_STAMP_FILE:-$HOME/.local/share/openclaw-build/version_build.json}"

stamp_field() {
  local key="$1"
  if [[ ! -f "$STAMP_FILE" ]]; then
    return 0
  fi
  if ! command -v node >/dev/null 2>&1; then
    return 0
  fi
  node -e 'const fs=require("fs"); const p=process.argv[1]; const k=process.argv[2]; try { const o=JSON.parse(fs.readFileSync(p,"utf8")); const v=Object.prototype.hasOwnProperty.call(o,k) ? String(o[k]) : ""; process.stdout.write(v); } catch {}' "$STAMP_FILE" "$key"
}

build_sha="$(stamp_field build_sha)"
build_time="$(stamp_field build_time_utc)"
package_version="$(stamp_field package_version)"

if [[ ! -x "$REAL_BIN" ]]; then
  echo "openclaw wrapper error: real binary missing at $REAL_BIN" >&2
  exit 1
fi

if [[ "${1-}" == "--version" || "${1-}" == "version" ]]; then
  base="$("$REAL_BIN" --version 2>/dev/null || true)"
  if [[ -z "$base" ]]; then
    base="${package_version:-unknown}"
  fi
  if [[ -n "$build_sha" ]]; then
    echo "$base build_sha=$build_sha build_time=$build_time"
  else
    echo "$base"
  fi
  exit 0
fi

if [[ "${1-}" == "gateway" ]]; then
  echo "openclaw_gateway build_sha=${build_sha:-unknown} version=${package_version:-unknown} build_time=${build_time:-unknown}"
fi

exec "$REAL_BIN" "$@"
