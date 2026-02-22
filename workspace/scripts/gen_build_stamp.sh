#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

stamp_path="${OPENCLAW_BUILD_STAMP_PATH:-$repo_root/workspace/version_build.json}"
build_sha="${OPENCLAW_BUILD_SHA:-$(git rev-parse HEAD)}"
build_time_utc="${OPENCLAW_BUILD_TIME_UTC:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
package_version="${OPENCLAW_BUILD_PACKAGE_VERSION:-unknown}"

if [[ "$package_version" == "unknown" ]] && command -v node >/dev/null 2>&1 && [[ -f package.json ]]; then
  package_version="$(node -e 'const fs=require("fs"); const p=JSON.parse(fs.readFileSync("package.json","utf8")); process.stdout.write(String(p.version || "unknown"));')"
fi

mkdir -p "$(dirname "$stamp_path")"
printf '{"build_sha":"%s","build_time_utc":"%s","package_version":"%s"}\n' "$build_sha" "$build_time_utc" "$package_version" > "$stamp_path"
echo "$stamp_path"
