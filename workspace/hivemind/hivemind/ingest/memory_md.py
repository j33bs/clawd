from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from ..models import KnowledgeUnit
from ..store import HiveMindStore

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MEMORY_PATH = REPO_ROOT / "workspace" / "MEMORY.md"

_HEADER_RE = re.compile(r"^(##|###)\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
_LESSON_RE = re.compile(r"\b(lesson|learned|learning|mistake|retro|retrospective)\b", re.IGNORECASE)


def parse_memory_chunks(text: str) -> List[Dict[str, str]]:
    chunks: List[Dict[str, str]] = []
    current_header = ""
    block_type = ""
    block_lines: List[str] = []

    def flush() -> None:
        nonlocal block_type, block_lines
        payload = "\n".join(block_lines).strip()
        if not payload:
            block_type = ""
            block_lines = []
            return
        body = payload
        if current_header:
            body = f"{current_header}\n{payload}".strip()
        kind = "lesson" if _LESSON_RE.search((current_header + "\n" + payload).strip()) else "fact"
        chunks.append({"kind": kind, "content": body})
        block_type = ""
        block_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        m = _HEADER_RE.match(line)
        if m:
            flush()
            current_header = m.group(2).strip()
            continue

        is_bullet = bool(_BULLET_RE.match(line))
        next_block = "bullet" if is_bullet else "text"

        if line.strip() == "":
            if block_lines:
                block_lines.append("")
            continue

        if block_type and block_type != next_block:
            flush()

        block_type = next_block
        block_lines.append(line)

    flush()
    return chunks


def ingest_memory_md(memory_path: Optional[Path] = None, store: Optional[HiveMindStore] = None) -> Dict[str, int]:
    target = Path(memory_path or DEFAULT_MEMORY_PATH)
    db = store or HiveMindStore()
    if not target.exists():
        return {"processed": 0, "stored": 0, "skipped": 0}

    text = target.read_text(encoding="utf-8")
    chunks = parse_memory_chunks(text)
    stored = 0
    skipped = 0
    for chunk in chunks:
        ku = KnowledgeUnit(
            kind=chunk["kind"],
            source="memory_md",
            agent_scope="main",
            ttl_days=None,
            metadata={"path": str(target)},
        )
        res = db.put(ku, chunk["content"])
        if res.get("stored"):
            stored += 1
        else:
            skipped += 1
    return {"processed": len(chunks), "stored": stored, "skipped": skipped}


if __name__ == "__main__":
    print(ingest_memory_md())
