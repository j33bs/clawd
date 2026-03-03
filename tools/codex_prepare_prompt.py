#!/usr/bin/env python3
"""Validate and normalize Codex prompts for CEL pre-spawn discipline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = (
    "GOAL",
    "INPUTS",
    "OUTPUTS",
    "CONSTRAINTS",
    "SUCCESS_CRITERIA",
)


@dataclass
class PromptValidationError(Exception):
    message: str
    missing_sections: list[str]

    def __str__(self) -> str:
        if not self.missing_sections:
            return self.message
        return f"{self.message}: missing={','.join(self.missing_sections)}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def estimate_tokens(text: str) -> int:
    # Lightweight deterministic estimate for planning/logging.
    return max(1, int(math.ceil(len(text) / 4)))


def _normalize_section_name(raw: str) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"\s+", "_", text)
    text = text.replace("-", "_")
    return text.upper()


def parse_required_sections(prompt_text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {name: [] for name in REQUIRED_SECTIONS}
    current: str | None = None

    for raw_line in prompt_text.splitlines():
        line = raw_line.rstrip("\n")
        heading_match = re.match(
            r"^\s{0,3}(?:#{1,6}\s*)?([A-Za-z][A-Za-z0-9_\s\-]{1,80})(?:\s*:)?\s*(.*)$",
            line,
        )
        if heading_match:
            candidate = _normalize_section_name(heading_match.group(1))
            if candidate in REQUIRED_SECTIONS:
                current = candidate
                trailing = heading_match.group(2).strip()
                if trailing:
                    sections[current].append(trailing)
                continue

        if current:
            sections[current].append(line)

    normalized = {
        name: "\n".join(lines).strip()
        for name, lines in sections.items()
    }
    missing = [name for name in REQUIRED_SECTIONS if not normalized.get(name)]
    if missing:
        raise PromptValidationError("prompt validation failed", missing)
    return normalized


def _safe_sha256(path: Path) -> str | None:
    try:
        with path.open("rb") as fh:
            digest = hashlib.sha256()
            while True:
                chunk = fh.read(8192)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def extract_referenced_files(prompt_text: str, sections: dict[str, str], *, cwd: Path) -> list[dict[str, Any]]:
    candidates: list[str] = []
    input_text = sections.get("INPUTS", "")

    patterns = [
        r"\[[^\]]+\]\(([^)]+)\)",
        r"`([^`\n]+)`",
        r"(?<![\w/])(?:\.{1,2}/|/)?[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+(?:\.[A-Za-z0-9._-]+)?",
    ]

    for pattern in patterns:
        for found in re.findall(pattern, input_text):
            candidates.append(str(found))

    # Also scan the full text for explicit markdown links.
    for found in re.findall(patterns[0], prompt_text):
        candidates.append(str(found))

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in candidates:
        cleaned = str(raw or "").strip().strip('"\'()[]<>,;')
        if not cleaned or "://" in cleaned:
            continue

        candidate = Path(cleaned).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (cwd / candidate).resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)

        exists = resolved.exists()
        is_file = resolved.is_file()
        size_bytes = None
        if exists:
            try:
                size_bytes = resolved.stat().st_size
            except OSError:
                size_bytes = None

        row: dict[str, Any] = {
            "path": str(resolved),
            "exists": bool(exists),
            "is_file": bool(is_file),
            "size_bytes": size_bytes,
        }
        if exists and is_file:
            file_hash = _safe_sha256(resolved)
            if file_hash:
                row["sha256"] = file_hash
        out.append(row)

    return out


def build_prepared_prompt_payload(
    prompt_text: str,
    *,
    source_path: Path,
    cwd: Path,
) -> dict[str, Any]:
    sections = parse_required_sections(prompt_text)
    normalized_prompt = "\n\n".join(f"{name}\n{sections[name]}" for name in REQUIRED_SECTIONS)
    task_hash = hashlib.sha256(normalized_prompt.encode("utf-8")).hexdigest()
    referenced_files = extract_referenced_files(prompt_text, sections, cwd=cwd)

    return {
        "schema": "codex_prepared_prompt.v1",
        "created_at": utc_now_iso(),
        "source_path": str(source_path.resolve()),
        "sections": sections,
        "normalized_prompt": normalized_prompt,
        "referenced_files": referenced_files,
        "metadata": {
            "char_count": len(normalized_prompt),
            "word_count": len(normalized_prompt.split()),
            "token_estimate": estimate_tokens(normalized_prompt),
            "task_hash": task_hash,
            "required_sections": list(REQUIRED_SECTIONS),
        },
    }


def write_prepared_prompt_file(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare/validate Codex prompt for CEL spawn")
    parser.add_argument("prompt_file", help="Path to markdown/text prompt")
    parser.add_argument(
        "--output",
        default="workspace/runtime/codex_prepared_prompt.json",
        help="Output JSON artifact path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prompt_path = Path(args.prompt_file).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    cwd = Path.cwd().resolve()

    if not prompt_path.exists() or not prompt_path.is_file():
        print(json.dumps({"ok": False, "error": f"prompt file not found: {prompt_path}"}, ensure_ascii=True))
        return 2

    try:
        prompt_text = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"unable to read prompt file: {exc}"}, ensure_ascii=True))
        return 2

    try:
        payload = build_prepared_prompt_payload(prompt_text, source_path=prompt_path, cwd=cwd)
    except PromptValidationError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": exc.message,
                    "missing_sections": exc.missing_sections,
                },
                ensure_ascii=True,
            )
        )
        return 1

    write_prepared_prompt_file(output_path, payload)
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output_path),
                "token_estimate": payload["metadata"]["token_estimate"],
                "task_hash": payload["metadata"]["task_hash"],
                "referenced_files": len(payload.get("referenced_files", [])),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
