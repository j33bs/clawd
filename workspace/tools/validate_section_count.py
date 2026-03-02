#!/usr/bin/env python3
"""
validate_section_count.py — warn when .section_count drifts from OPEN_QUESTIONS.md

Compares the integer in workspace/governance/.section_count against
the actual number of Roman-numeral sections parsed from OPEN_QUESTIONS.md.

Exit codes:
  0  — counts match (or --warn-only flag set)
  1  — counts differ AND --warn-only not set

Usage:
  python3 workspace/tools/validate_section_count.py           # strict
  python3 workspace/tools/validate_section_count.py --warn-only  # warn only (for nightly)
"""
from __future__ import annotations

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OQ_PATH    = os.path.join(REPO_ROOT, "workspace", "governance", "OPEN_QUESTIONS.md")
COUNT_FILE = os.path.join(REPO_ROOT, "workspace", "governance", ".section_count")

# Matches Roman numeral section headers: "## XII. Title", "## CXLII: ...", "## CXLII —"
# NOTE: "CXLI (cont.)" injections do NOT match intentionally — they are not canonical sections.
# .section_count tracks parseable canonical sections, not the nominal highest Roman numeral.
_HEADER_RE = re.compile(r"^#{1,3}\s+([IVXLCDM]+)\s*[.:\-—]", re.MULTILINE)


def count_sections_in_file(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return len(_HEADER_RE.findall(text))


def read_count_file(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        return int(f.read().strip())


def main() -> int:
    warn_only = "--warn-only" in sys.argv

    try:
        filed = read_count_file(COUNT_FILE)
    except FileNotFoundError:
        print(f"[validate_section_count] WARN: {COUNT_FILE} not found", file=sys.stderr)
        return 0 if warn_only else 1
    except ValueError as e:
        print(f"[validate_section_count] WARN: could not parse .section_count: {e}", file=sys.stderr)
        return 0 if warn_only else 1

    try:
        parsed = count_sections_in_file(OQ_PATH)
    except FileNotFoundError:
        print(f"[validate_section_count] WARN: {OQ_PATH} not found", file=sys.stderr)
        return 0 if warn_only else 1

    delta = filed - parsed
    if delta == 0:
        print(f"[validate_section_count] OK  filed={filed}  parsed={parsed}  delta={delta}")
        return 0

    level = "WARN" if warn_only else "ERROR"
    print(
        f"[validate_section_count] {level}  filed={filed}  parsed={parsed}  delta={delta}"
        f"  (.section_count is {'ahead' if delta > 0 else 'behind'} by {abs(delta)})",
        file=sys.stderr,
    )
    return 0 if warn_only else 1


if __name__ == "__main__":
    sys.exit(main())
