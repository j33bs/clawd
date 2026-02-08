#!/usr/bin/env python3
"""
Quarantine untracked artifacts into .workspace_artifacts/.
Use --apply to move, otherwise dry-run.
"""
import argparse
import datetime as dt
import os
import shutil
import subprocess
from pathlib import Path


def list_untracked():
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z"],
        capture_output=True,
        text=False,
        check=False,
    )
    data = result.stdout or b""
    entries = data.split(b"\x00")
    paths = []
    for entry in entries:
        if not entry:
            continue
        try:
            status = entry[:2].decode("utf-8", errors="ignore")
            path = entry[3:].decode("utf-8", errors="ignore")
        except Exception:
            continue
        if status == "??":
            paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description="Quarantine untracked artifacts")
    parser.add_argument("--apply", action="store_true", help="Move untracked files into quarantine")
    parser.add_argument("--dest", type=str, default=None, help="Override destination folder")
    args = parser.parse_args()

    paths = list_untracked()
    if not paths:
        print("No untracked artifacts found.")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = Path(args.dest) if args.dest else Path(".workspace_artifacts") / stamp
    if args.apply:
        dest.mkdir(parents=True, exist_ok=True)

    for path in paths:
        if args.apply:
            src = Path(path)
            target = dest / src
            target.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.move(str(src), str(target))
            print(f"moved: {path} -> {target}")
        else:
            print(f"would move: {path} -> {dest / path}")

    if not args.apply:
        print("")
        print("Dry run complete. Re-run with --apply to move.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
