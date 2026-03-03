#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
hooks_dir="$(git rev-parse --git-dir)/hooks"
mkdir -p "$hooks_dir"

install_hook() {
  local hook_name="$1"
  local hook_path="$hooks_dir/$hook_name"
  cat > "$hook_path" <<'HOOK'
#!/usr/bin/env bash
set +e
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
if [[ -z "$repo_root" ]]; then
  exit 0
fi
bash "$repo_root/workspace/scripts/openclaw_autoupdate.sh" || true
exit 0
HOOK
  chmod +x "$hook_path"
  echo "Installed: $hook_path"
}

install_hook post-merge
install_hook post-checkout

echo "OK: runtime autoupdate hooks installed"
