#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "UNKNOWN"
  exit 1
fi

repo_root_phys="$(cd "${repo_root}" && pwd -P)"

if [[ "${repo_root_phys}" == */.worktrees/livewire ]]; then
  echo "LIVEWIRE"
else
  echo "CANON"
fi
