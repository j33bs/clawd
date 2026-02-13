#!/usr/bin/env python3
"""
Handoff writer.

Creates a timestamped file in:
  workspace/handoffs/YYYY-MM-DD-HHmm-{label}.md

If no content is provided via --content, reads from stdin.
"""

import argparse
import datetime as dt
import re
import sys
from pathlib import Path


def _sanitize_label(label: str) -> str:
    label = label.strip().lower()
    label = re.sub(r"[^a-z0-9._-]+", "_", label)
    label = re.sub(r"_+", "_", label).strip("_")
    return label or "handoff"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label", help="Short label used in filename and title")
    ap.add_argument("--from", dest="from_agent", default="claude-code", help="Agent name for metadata")
    ap.add_argument("--status", default="pending", help="pending|done|blocked (freeform)")
    ap.add_argument("--content", default=None, help="Body content; if omitted, read stdin")
    args = ap.parse_args()

    label = _sanitize_label(args.label)
    now = dt.datetime.now(dt.timezone.utc)
    ts_file = now.strftime("%Y-%m-%d-%H%M")
    ts_iso = now.isoformat()

    out_dir = Path("workspace/handoffs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ts_file}-{label}.md"

    content = args.content
    if content is None:
        # If stdin is interactive and no --content provided, default to empty Notes.
        if sys.stdin.isatty():
            content = ""
        else:
            content = sys.stdin.read()

    body = (
        f"# Handoff: {args.label}\n"
        f"- **From**: {args.from_agent}\n"
        f"- **Date**: {ts_iso}\n"
        f"- **Status**: {args.status}\n\n"
        "## Notes\n"
        f"{content.rstrip()}\n"
    )
    out_path.write_text(body, encoding="utf-8")
    print(f"ok: wrote {out_path.as_posix()}")


if __name__ == "__main__":
    main()

