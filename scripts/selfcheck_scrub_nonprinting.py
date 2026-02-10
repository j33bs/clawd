#!/usr/bin/env python3

import re
import sys
from pathlib import Path


def main() -> int:
    scrub_path = Path(__file__).resolve().parent / "scrub_secrets.ps1"
    text = scrub_path.read_text(encoding="utf-8")
    checks_run = 0
    failures = []

    checks_run += 1
    write_output_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("Write-Output ")
    ]
    allowed = {
        'Write-Output "WORKTREE hits: $($worktreeHits.Count)"',
        'Write-Output "History files implicated: $($historyFiles.Count)"',
    }
    if set(write_output_lines) != allowed:
        failures.append("output_lines_not_count_only")

    checks_run += 1
    if "Write-Host" in text:
        failures.append("write_host_present")

    checks_run += 1
    if re.search(r"Write-Output\s+\$(rawWorktree|line|rawHistory|Matches)\b", text):
        failures.append("raw_match_output_present")

    checks_run += 1
    if "grep -nE" not in text or "2>$null" not in text:
        failures.append("grep_capture_guard_missing")

    checks_run += 1
    if "'^([^:]+:[0-9]+):'" not in text:
        failures.append("path_line_transform_missing")

    checks_run += 1
    if "Set-Content -LiteralPath $worktreeOut -Value $worktreeHits" not in text:
        failures.append("worktree_write_missing")

    print(f"checks_run: {checks_run}")
    print(f"checks_failed: {len(failures)}")
    print(f"selfcheck_passed: {1 if not failures else 0}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
