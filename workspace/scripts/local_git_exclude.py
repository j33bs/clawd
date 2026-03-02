#!/usr/bin/env python3
"""Local-only git exclude helper for C_Lawd hygiene.

Default mode is advice-only. Installation into git metadata is opt-in.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence, TextIO

BEGIN_MARKER = "# BEGIN OPENCLAW LOCAL EXCLUDES (generated)"
END_MARKER = "# END OPENCLAW LOCAL EXCLUDES"


def get_recommended_excludes() -> List[str]:
    return [
        ".worktrees/",
        "workspace/research/pdfs/",
        "workspace/state_runtime/memory_ext/",
        "workspace/audit/_scratch_local/",
    ]


def format_exclude_block(patterns: List[str]) -> str:
    seen = set()
    ordered: List[str] = []
    for item in patterns:
        value = str(item).strip()
        if not value or value in seen:
            continue
        ordered.append(value)
        seen.add(value)

    lines = [BEGIN_MARKER]
    lines.extend(ordered)
    lines.append(END_MARKER)
    return "\n".join(lines) + "\n"


def merge_exclude(existing_text: str, new_block: str) -> str:
    existing = existing_text or ""
    begin = existing.find(BEGIN_MARKER)
    end = existing.find(END_MARKER)

    if begin != -1 and end != -1 and end >= begin:
        end_after = end + len(END_MARKER)
        if end_after < len(existing) and existing[end_after:end_after + 1] == "\n":
            end_after += 1
        merged = existing[:begin] + new_block + existing[end_after:]
        return merged

    if not existing:
        return new_block

    suffix = "" if existing.endswith("\n") else "\n"
    return existing + suffix + new_block


def _resolve_exclude_path() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--git-path", "info/exclude"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError("not_a_git_repo")
    target = (proc.stdout or "").strip()
    if not target:
        raise RuntimeError("missing_git_exclude_path")
    return Path(target)


def _install_block(block: str, out: TextIO) -> int:
    if os.getenv("OPENCLAW_ALLOW_LOCAL_GIT_EXCLUDE_WRITE") != "1":
        out.write("FAIL: install is disabled. Set OPENCLAW_ALLOW_LOCAL_GIT_EXCLUDE_WRITE=1 to proceed.\n")
        return 2

    try:
        path = _resolve_exclude_path()
    except RuntimeError as exc:
        out.write("FAIL: unable to resolve git exclude path ({0}).\n".format(exc))
        return 2

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    merged = merge_exclude(existing, block)
    if merged == existing:
        out.write("local excludes already installed (no changes): {0}\n".format(path))
        return 0

    path.write_text(merged, encoding="utf-8")
    out.write("installed/updated block: {0}\n".format(path))
    return 0


def run(argv: Optional[Sequence[str]] = None, out: Optional[TextIO] = None) -> int:
    output = out or sys.stdout

    parser = argparse.ArgumentParser(description="Manage local-only git excludes for OpenClaw")
    parser.add_argument("--print", action="store_true", dest="print_block", help="Print recommended exclude block")
    parser.add_argument("--install", action="store_true", help="Install/replace marker block in .git/info/exclude")
    args = parser.parse_args(list(argv) if argv is not None else None)

    block = format_exclude_block(get_recommended_excludes())

    if args.install:
        return _install_block(block, output)

    # Advice-only default path.
    output.write(block)
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
