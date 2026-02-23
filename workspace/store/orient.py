#!/usr/bin/env python3
"""
orient.py — c_lawd session orientation hook.

Run this before appending to OPEN_QUESTIONS.md.
Prints the next section number as a Roman numeral, a ready-to-paste
header template, and increments .section_count.

Usage:
    python workspace/store/orient.py
    python workspace/store/orient.py --author "c_lawd"
    python workspace/store/orient.py --dry-run
    python workspace/store/orient.py --verify        # cross-check against file

Flags:
    --author NAME    Include author name in the header template
    --dry-run        Print output but do NOT write .section_count
    --verify         Count actual sections in OPEN_QUESTIONS.md and warn on mismatch
    --title TITLE    Include title in the header template (optional)
"""
from __future__ import annotations
import argparse
import os
import re
import sys
from datetime import date

WORKSPACE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COUNT_FILE = os.path.join(WORKSPACE, "governance", ".section_count")
OQ_PATH    = os.path.join(WORKSPACE, "governance", "OPEN_QUESTIONS.md")

# ---------------------------------------------------------------------------
# Roman numeral conversion
# ---------------------------------------------------------------------------

_VAL  = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
_SYMS = ['M', 'CM', 'D', 'CD', 'C', 'XC', 'L', 'XL', 'X', 'IX', 'V', 'IV', 'I']


def int_to_roman(n: int) -> str:
    """Convert a positive integer to a Roman numeral string."""
    if n <= 0:
        raise ValueError(f"Section number must be positive, got {n}")
    result = ""
    for val, sym in zip(_VAL, _SYMS):
        while n >= val:
            result += sym
            n -= val
    return result


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def read_count() -> int:
    """Read current section count from .section_count."""
    if not os.path.exists(COUNT_FILE):
        print(f"  ERROR: .section_count not found at {COUNT_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(COUNT_FILE, "r") as f:
        raw = f.read().strip()
    if not raw.isdigit():
        print(f"  ERROR: .section_count contains non-integer value: {repr(raw)}", file=sys.stderr)
        sys.exit(1)
    return int(raw)


def write_count(n: int) -> None:
    """Write updated section count to .section_count."""
    with open(COUNT_FILE, "w") as f:
        f.write(str(n) + "\n")


def count_actual_sections() -> int:
    """Count Roman-numeral-headed sections in OPEN_QUESTIONS.md."""
    if not os.path.exists(OQ_PATH):
        return -1
    pattern = re.compile(r'^## [IVXLCDM]+\.', re.IGNORECASE)
    count = 0
    with open(OQ_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if pattern.match(line.rstrip()):
                count += 1
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="c_lawd session orientation hook — get next section number before appending."
    )
    parser.add_argument("--author",  default="",  help="Author name for header template")
    parser.add_argument("--title",   default="",  help="Section title for header template")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print output but do not update .section_count")
    parser.add_argument("--verify",  action="store_true",
                        help="Cross-check .section_count against actual section count in file")
    args = parser.parse_args()

    current_n  = read_count()
    next_n     = current_n + 1   # may be overridden by --verify
    next_roman = int_to_roman(next_n)
    today      = date.today().isoformat()

    # --- Build header template ---
    author_part = args.author if args.author else "[Author]"
    title_part  = args.title  if args.title  else "[Title]"
    header = f"## {next_roman}. {author_part} — {title_part} ({today})"

    # --- Output ---
    print()
    print("── CorrespondenceStore orientation ──")
    print(f"  Current section count : {current_n}")
    print(f"  Your section number   : {next_roman}  ({next_n})")
    print()
    print("  Header template:")
    print(f"    {header}")
    print()

    # --- Verify (optional) ---
    # When a mismatch is found, override next_n so write_count uses the corrected value.
    if args.verify:
        actual = count_actual_sections()
        if actual == -1:
            print(f"  ⚠  VERIFY: OPEN_QUESTIONS.md not found at {OQ_PATH}", file=sys.stderr)
        elif actual != current_n:
            direction = "ahead of" if current_n > actual else "behind"
            print(f"  ⚠  VERIFY: .section_count ({current_n}) is {direction} file ({actual} sections)")
            if current_n > actual:
                print(f"     Likely cause: orient.py run without filing the section (slot reserved but unused)")
            else:
                print(f"     Likely cause: section filed without running orient.py (collision risk)")
            corrected_next = actual + 1
            corrected_roman = int_to_roman(corrected_next)
            author_part = args.author if args.author else "[Author]"
            header = f"## {corrected_roman}. {author_part} — {title_part} ({today})"
            print(f"     Corrected next section: {corrected_roman} ({corrected_next})")
            print(f"\n  Corrected header template:")
            print(f"    {header}")
            print()
            # Override next_n so write_count uses the corrected value, not the stale one
            next_n = corrected_next
        else:
            print(f"  ✅ VERIFY: .section_count matches file ({actual} sections)")
            print()

    # --- Write (unless dry-run) ---
    if args.dry_run:
        print("  [dry-run] .section_count NOT updated")
    else:
        write_count(next_n)
        print(f"  .section_count updated: {current_n} → {next_n}")

    print()
    print("  Write your section, then commit both OPEN_QUESTIONS.md and .section_count.")
    print()


if __name__ == "__main__":
    main()
