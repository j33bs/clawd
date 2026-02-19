from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

from ..models import KnowledgeUnit
from ..store import HiveMindStore

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_HANDOFFS_DIR = REPO_ROOT / "workspace" / "handoffs"

_KEY_RE = re.compile(r"^\s*(status|from|date)\s*:\s*(.+?)\s*$", re.IGNORECASE)


def parse_frontmatter(text: str) -> Dict[str, str]:
    meta: Dict[str, str] = {"status": "", "from": "", "date": ""}
    lines = text.splitlines()

    scan_lines = lines[:40]
    if lines and lines[0].strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                scan_lines = lines[1:idx]
                break

    for line in scan_lines:
        m = _KEY_RE.match(line)
        if not m:
            continue
        meta[m.group(1).lower()] = m.group(2).strip()
    return meta


def ingest_handoffs(handoffs_dir: Optional[Path] = None, store: Optional[HiveMindStore] = None) -> Dict[str, int]:
    src_dir = Path(handoffs_dir or DEFAULT_HANDOFFS_DIR)
    db = store or HiveMindStore()
    if not src_dir.exists():
        return {"processed": 0, "stored": 0, "skipped": 0}

    processed = 0
    stored = 0
    skipped = 0

    for path in sorted(src_dir.glob("*.md")):
        processed += 1
        text = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        ku = KnowledgeUnit(
            kind="handoff",
            source="handoffs",
            agent_scope="shared",
            ttl_days=30,
            metadata={
                "path": str(path),
                "status": meta.get("status", ""),
                "from": meta.get("from", ""),
                "date": meta.get("date", ""),
            },
        )
        res = db.put(ku, text)
        if res.get("stored"):
            stored += 1
        else:
            skipped += 1

    return {"processed": processed, "stored": stored, "skipped": skipped}


if __name__ == "__main__":
    print(ingest_handoffs())
