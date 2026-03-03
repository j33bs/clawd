#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "FAIL: not inside a git repository" >&2
  exit 1
fi

tmp_root="$(mktemp -d /tmp/worktree-boundary-test.XXXXXX)"
canon_path="${tmp_root}/canon"
livewire_path="${tmp_root}/livewire"
canon_branch="test/worktree-boundary-canon-$$"
livewire_branch="test/worktree-boundary-livewire-$$"
test_file="README.md"

cleanup() {
  set +e
  git -C "${repo_root}" worktree remove --force "${canon_path}" >/dev/null 2>&1
  git -C "${repo_root}" worktree remove --force "${livewire_path}" >/dev/null 2>&1
  git -C "${repo_root}" branch -D "${canon_branch}" >/dev/null 2>&1
  git -C "${repo_root}" branch -D "${livewire_branch}" >/dev/null 2>&1
  rm -rf "${tmp_root}"
}
trap cleanup EXIT

git -C "${repo_root}" worktree add -b "${canon_branch}" "${canon_path}" HEAD >/dev/null
git -C "${repo_root}" worktree add -b "${livewire_branch}" "${livewire_path}" HEAD >/dev/null

echo "# canon-boundary-test-$$" >> "${canon_path}/${test_file}"
(
  cd "${canon_path}"
  set +e
  MODE=CANON "${repo_root}/tools/guard_worktree_boundary.sh"
  canon_rc=$?
  set -e
  if [[ "${canon_rc}" -eq 0 ]]; then
    echo "FAIL: CANON mode should fail-closed on non-allowlisted drift" >&2
    exit 1
  fi
)
canon_non_snapshot_status="$(git -C "${canon_path}" status --porcelain=v1 | grep -v ' workspace/audit/worktree_dirty_snapshot_' || true)"
if [[ -z "${canon_non_snapshot_status}" ]]; then
  echo "FAIL: CANON mode should preserve drift for explicit operator action" >&2
  exit 1
fi

canon_snapshot="$(ls -1t "${canon_path}"/workspace/audit/worktree_dirty_snapshot_*_CANON.md 2>/dev/null | head -n 1 || true)"
if [[ -z "${canon_snapshot}" || ! -f "${canon_snapshot}" ]]; then
  echo "FAIL: CANON mode did not produce snapshot evidence" >&2
  exit 1
fi

echo "# livewire-boundary-test-$$" >> "${livewire_path}/${test_file}"
(
  cd "${livewire_path}"
  MODE=LIVEWIRE "${repo_root}/tools/guard_worktree_boundary.sh"
)
if [[ -z "$(git -C "${livewire_path}" status --porcelain=v1)" ]]; then
  echo "FAIL: LIVEWIRE mode should preserve dirty changes" >&2
  exit 1
fi

livewire_snapshot="$(ls -1t "${livewire_path}"/workspace/audit/worktree_dirty_snapshot_*_LIVEWIRE.md 2>/dev/null | head -n 1 || true)"
if [[ -z "${livewire_snapshot}" || ! -f "${livewire_snapshot}" ]]; then
  echo "FAIL: LIVEWIRE mode did not produce snapshot evidence" >&2
  exit 1
fi

echo "ok"
