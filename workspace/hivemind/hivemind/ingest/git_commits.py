from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..models import KnowledgeUnit
from ..store import HiveMindStore

REPO_ROOT = Path(__file__).resolve().parents[4]


def _run(repo_root: Path, args: List[str]) -> str:
    proc = subprocess.run(args, cwd=str(repo_root), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "git command failed")
    return proc.stdout


def extract_diff_blocks(diff_text: str) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = []
    current_file = ""
    current: List[str] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        body = "\n".join(current).strip()
        if body:
            blocks.append((current_file or "unknown", body))
        current = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            flush()
            parts = line.split()
            current_file = parts[2][2:] if len(parts) >= 3 and parts[2].startswith("a/") else "unknown"
            continue
        if line.startswith("@@"):
            flush()
            current = [line]
            continue
        if not current:
            continue
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-", " ")):
            current.append(line)

    flush()
    return blocks


def ingest_head_commit(repo_root: Optional[Path] = None, store: Optional[HiveMindStore] = None) -> Dict[str, int]:
    root = Path(repo_root or REPO_ROOT)
    db = store or HiveMindStore()
    sha = _run(root, ["git", "rev-parse", "HEAD"]).strip()
    show = _run(root, ["git", "show", "--patch", "--stat", "HEAD"])
    blocks = extract_diff_blocks(show)

    if not blocks:
        blocks = [("summary", show.strip())] if show.strip() else []

    stored = 0
    skipped = 0
    for idx, (file_path, snippet) in enumerate(blocks):
        ku = KnowledgeUnit(
            kind="code_snippet",
            source=f"git:{sha}",
            agent_scope="shared",
            ttl_days=None,
            metadata={"file": file_path, "index": idx},
        )
        res = db.put(ku, snippet)
        if res.get("stored"):
            stored += 1
        else:
            skipped += 1

    return {"processed": len(blocks), "stored": stored, "skipped": skipped}


if __name__ == "__main__":
    print(ingest_head_commit())
