#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "workspace" / "OPEN_QUESTIONS.md"
DEFAULT_JSON = REPO_ROOT / "workspace" / "reports" / "commitments.json"
DEFAULT_MD = REPO_ROOT / "workspace" / "reports" / "commitments.md"

HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
PATTERNS = [
    re.compile(r"\bI will\b", re.IGNORECASE),
    re.compile(r"\bbefore next audit\b", re.IGNORECASE),
    re.compile(r"\bcommitted to\b", re.IGNORECASE),
    re.compile(r"\bwe will\b", re.IGNORECASE),
    re.compile(r"\bI commit to\b", re.IGNORECASE),
]


def _section_path(stack: list[tuple[int, str]]) -> str:
    return " > ".join(title for _, title in stack)


def extract_commitments(markdown: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    stack: list[tuple[int, str]] = []
    for idx, line in enumerate(markdown.splitlines(), start=1):
        hm = HEADING_RE.match(line)
        if hm:
            level = len(hm.group(1))
            title = hm.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            continue
        text = line.strip()
        if not text:
            continue
        hit = next((p for p in PATTERNS if p.search(text)), None)
        if not hit:
            continue
        snippet = text[:140]
        results.append(
            {
                "line": idx,
                "section_path": _section_path(stack),
                "pattern": hit.pattern,
                "snippet": snippet,
            }
        )
    return results


def write_reports(commitments: list[dict[str, Any]], *, json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"count": len(commitments), "commitments": commitments}
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Commitments Extracted from OPEN_QUESTIONS",
        "",
        f"- total: {len(commitments)}",
        "",
        "| line | section | snippet |",
        "|---:|---|---|",
    ]
    for item in commitments:
        section = str(item.get("section_path", "")).replace("|", "\\|")
        snippet = str(item.get("snippet", "")).replace("|", "\\|")
        lines.append(f"| {int(item.get('line', 0))} | {section} | {snippet} |")
    if not commitments:
        lines.append("| 0 | (none) | (none) |")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract commitment language from OPEN_QUESTIONS")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON))
    parser.add_argument("--md-output", default=str(DEFAULT_MD))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    markdown = input_path.read_text(encoding="utf-8") if input_path.exists() else ""
    commitments = extract_commitments(markdown)
    write_reports(commitments, json_path=Path(args.json_output), md_path=Path(args.md_output))
    result = {
        "ok": True,
        "input": str(input_path),
        "count": len(commitments),
        "json_output": str(args.json_output),
        "md_output": str(args.md_output),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

