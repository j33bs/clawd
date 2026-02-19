#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    kb_root = repo_root / "workspace" / "knowledge_base"
    if str(kb_root) not in sys.path:
        sys.path.insert(0, str(kb_root))

    from graph.store import KnowledgeGraphStore  # noqa: WPS433

    proc = subprocess.run(
        ["git", "-C", str(repo_root), "log", "--oneline", "-50"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print("Decisions indexed: 0 (git log unavailable)")
        return 1

    pattern = re.compile(r"^(feat|fix|harden|sec|const)(\([^)]+\))?:", re.IGNORECASE)
    store = KnowledgeGraphStore(kb_root / "data")
    indexed = 0
    for line in (proc.stdout or "").splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        sha, message = parts
        if not pattern.match(message):
            continue
        store.add_entity(
            name=message[:80],
            entity_type="decision",
            content=f"{sha} {message}",
            source=f"git:{sha}",
            metadata={"commit": sha},
        )
        indexed += 1

    print(f"Decisions indexed: {indexed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
