#!/usr/bin/env python3

import argparse
import re
import shutil
from pathlib import Path

PATTERN = re.compile(
    r"(?i)(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z\-_]{35}|-----BEGIN[ A-Z_-]{0,20}K[E]Y-----|bearer\s+[A-Za-z0-9._\-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
)
REPLACEMENT = "[REDACTED_SECRET]"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hits-file", default="scrub_worktree_hits.txt")
    args = parser.parse_args()

    hits_path = Path(args.hits_file)
    if not hits_path.exists():
        print("files_listed: 0")
        print("files_modified: 0")
        return 0

    files = set()
    for line in hits_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        path_part = line.split(":", 1)[0]
        if path_part:
            files.add(Path(path_part))

    files_modified = 0
    for file_path in sorted(files):
        if not file_path.exists() or not file_path.is_file():
            continue
        original = file_path.read_text(encoding="utf-8", errors="ignore")
        redacted = PATTERN.sub(REPLACEMENT, original)
        if redacted != original:
            backup_path = Path(str(file_path) + ".bak")
            shutil.copy2(file_path, backup_path)
            file_path.write_text(redacted, encoding="utf-8")
            files_modified += 1

    print(f"files_listed: {len(files)}")
    print(f"files_modified: {files_modified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
