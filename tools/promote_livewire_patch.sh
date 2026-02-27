#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "FAIL: not inside a git repository" >&2
  exit 1
fi
cd "${repo_root}"

livewire_path="${repo_root}/.worktrees/livewire"
if [[ ! -d "${livewire_path}" ]]; then
  echo "FAIL: LIVEWIRE worktree not found at ${livewire_path}" >&2
  exit 1
fi
if ! git -C "${livewire_path}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "FAIL: LIVEWIRE path is not a git worktree: ${livewire_path}" >&2
  exit 1
fi

livewire_status="$(git -C "${livewire_path}" status --porcelain=v1)"
if [[ -z "${livewire_status}" ]]; then
  echo "FAIL: LIVEWIRE has no changes to promote" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
patch_path="${repo_root}/workspace/audit/livewire_patch_${timestamp}.patch"
git -C "${livewire_path}" diff > "${patch_path}"
if [[ ! -s "${patch_path}" ]]; then
  echo "FAIL: generated patch is empty (LIVEWIRE may only have untracked files)" >&2
  exit 1
fi

MODE=CANON "${repo_root}/tools/guard_worktree_boundary.sh"
if [[ -n "$(git -C "${repo_root}" status --porcelain=v1)" ]]; then
  echo "FAIL: CANON must be clean before patch apply" >&2
  exit 1
fi

if ! git -C "${repo_root}" apply --index "${patch_path}"; then
  echo "FAIL: patch apply failed; resolve conflicts manually" >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  python3 -m unittest -q
fi

if command -v node >/dev/null 2>&1 && [[ -f "${repo_root}/package.json" ]]; then
  node --test
else
  echo "note: node --test skipped (node or package.json unavailable)"
fi

if git -C "${repo_root}" diff --cached --quiet; then
  echo "FAIL: no staged changes after patch apply" >&2
  exit 1
fi

git -C "${repo_root}" commit \
  -m "chore(livewire): promote patch ${timestamp}" \
  -m "livewire_patch: ${patch_path#${repo_root}/}"

echo "promoted_patch=${patch_path}"
