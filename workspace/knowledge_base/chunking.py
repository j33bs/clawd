from __future__ import annotations

import re
from typing import Iterable

from embeddings.driver_mlx import ACCEL_MODEL_ID, CANONICAL_MODEL_ID

MODEL_CHUNKING = {
    CANONICAL_MODEL_ID: {"max_tokens": 1200, "overlap_tokens": 120},
    ACCEL_MODEL_ID: {"max_tokens": 450, "overlap_tokens": 50},
}

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def tokenize_approx(text: str) -> list[str]:
    return _TOKEN_RE.findall(str(text or ""))


def count_tokens(text: str) -> int:
    return len(tokenize_approx(text))


def _markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading = ""
    current: list[str] = []

    for raw_line in str(text or "").splitlines():
        line = raw_line.rstrip()
        match = _HEADING_RE.match(line)
        if match:
            body = "\n".join(current).strip()
            if body or heading:
                sections.append((heading, body))
            heading = match.group(2).strip()
            current = []
            continue
        current.append(line)

    body = "\n".join(current).strip()
    if body or heading:
        sections.append((heading, body))

    if not sections:
        sections.append(("", str(text or "").strip()))

    return sections


def _token_windows(tokens: list[str], max_tokens: int, overlap_tokens: int) -> Iterable[list[str]]:
    if not tokens:
        return []
    windows: list[list[str]] = []
    start = 0
    while start < len(tokens):
        end = min(len(tokens), start + max_tokens)
        windows.append(tokens[start:end])
        if end >= len(tokens):
            break
        start = max(0, end - overlap_tokens)
    return windows


def _chunk_section_text(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current_tokens: list[str] = []

    for para in paragraphs:
        para_tokens = tokenize_approx(para)
        if len(para_tokens) > max_tokens:
            if current_tokens:
                chunks.append(" ".join(current_tokens))
                current_tokens = current_tokens[-overlap_tokens:] if overlap_tokens > 0 else []
            for win in _token_windows(para_tokens, max_tokens=max_tokens, overlap_tokens=overlap_tokens):
                chunks.append(" ".join(win))
            current_tokens = chunks[-1].split()[-overlap_tokens:] if overlap_tokens > 0 and chunks else []
            continue

        if current_tokens and (len(current_tokens) + len(para_tokens) > max_tokens):
            chunks.append(" ".join(current_tokens))
            current_tokens = current_tokens[-overlap_tokens:] if overlap_tokens > 0 else []

        current_tokens.extend(para_tokens)

    if current_tokens:
        chunks.append(" ".join(current_tokens))

    return [c.strip() for c in chunks if c.strip()]


def chunk_markdown(text: str, model_id: str) -> list[dict]:
    if model_id not in MODEL_CHUNKING:
        raise ValueError(f"Unsupported model_id for chunking: {model_id}")

    cfg = MODEL_CHUNKING[model_id]
    max_tokens = int(cfg["max_tokens"])
    overlap_tokens = int(cfg["overlap_tokens"])

    chunks: list[dict] = []
    section_idx = 0

    for heading, section_text in _markdown_sections(text):
        section_idx += 1
        body = section_text.strip()
        if not body:
            continue
        part_chunks = _chunk_section_text(body, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
        for part_idx, chunk_text in enumerate(part_chunks, start=1):
            full_text = chunk_text
            if heading:
                full_text = f"{heading}\n\n{chunk_text}"
            chunks.append(
                {
                    "section": heading,
                    "chunk_id": f"s{section_idx:04d}-c{part_idx:04d}",
                    "text": full_text,
                    "tokens": count_tokens(full_text),
                }
            )

    return chunks
