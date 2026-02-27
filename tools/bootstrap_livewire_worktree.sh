#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "FAIL: not inside a git repository" >&2
  exit 1
fi

livewire_path="${repo_root}/.worktrees/livewire"
exclude_file="${repo_root}/.git/info/exclude"

mkdir -p "${repo_root}/.worktrees"
mkdir -p "$(dirname "${exclude_file}")"
touch "${exclude_file}"

if ! grep -Fxq ".worktrees/" "${exclude_file}"; then
  printf '%s\n' ".worktrees/" >> "${exclude_file}"
fi

is_registered=0
while IFS= read -r wt; do
  if [[ "${wt}" == "${livewire_path}" ]]; then
    is_registered=1
    break
  fi
done < <(git -C "${repo_root}" worktree list --porcelain | awk '/^worktree /{print substr($0,10)}')

if [[ "${is_registered}" -eq 0 ]]; then
  if [[ -e "${livewire_path}" ]]; then
    echo "FAIL: ${livewire_path} exists but is not a registered worktree" >&2
    exit 1
  fi
  if ! git -C "${repo_root}" rev-parse --verify origin/main >/dev/null 2>&1; then
    echo "FAIL: origin/main not found; fetch origin first" >&2
    exit 1
  fi
  git -C "${repo_root}" worktree add -B livewire "${livewire_path}" origin/main
fi

cd "${livewire_path}"
pwd -P
