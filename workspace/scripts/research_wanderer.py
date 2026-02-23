#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPEN_QUESTIONS = REPO_ROOT / "workspace" / "OPEN_QUESTIONS.md"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TOKEN_RE = re.compile(r"\b[A-Za-z0-9_-]{24,}\b")
ARABIC_RE = re.compile(r"^\s*(\d+)\.\s+")
ROMAN_RE = re.compile(r"^\s*([IVXLCDM]+)\.\s+", re.IGNORECASE)


@dataclass
class QuestionCandidate:
    text: str
    significance: float


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _commit_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True).strip()


def _sanitize(text: str) -> str:
    cleaned = EMAIL_RE.sub("[REDACTED_EMAIL]", str(text))
    cleaned = TOKEN_RE.sub("[REDACTED_TOKEN]", cleaned)
    return " ".join(cleaned.split())


def _roman_to_int(value: str) -> int:
    value = value.upper()
    mapping = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(value):
        cur = mapping.get(ch, 0)
        if cur < prev:
            total -= cur
        else:
            total += cur
            prev = cur
    return total


def _int_to_roman(num: int) -> str:
    vals = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    out = []
    n = max(1, int(num))
    for value, token in vals:
        while n >= value:
            out.append(token)
            n -= value
    return "".join(out)


def _next_index_style(existing: str) -> tuple[str, int]:
    max_arabic = 0
    max_roman = 0
    for line in existing.splitlines():
        ma = ARABIC_RE.match(line)
        if ma:
            max_arabic = max(max_arabic, int(ma.group(1)))
        mr = ROMAN_RE.match(line)
        if mr:
            max_roman = max(max_roman, _roman_to_int(mr.group(1)))
    if max_arabic > 0:
        return "arabic", max_arabic + 1
    if max_roman > 0:
        return "roman", max_roman + 1
    return "arabic", 1


def _extract_candidates(payload: Any) -> list[QuestionCandidate]:
    out: list[QuestionCandidate] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("questions"), list):
            payload = payload.get("questions")
        else:
            payload = [payload]
    if not isinstance(payload, list):
        return out
    for item in payload:
        if isinstance(item, str):
            out.append(QuestionCandidate(text=item, significance=1.0))
            continue
        if not isinstance(item, dict):
            continue
        text = item.get("question") or item.get("text") or item.get("prompt")
        if not text:
            continue
        sig = item.get("significance", item.get("score", 0.0))
        try:
            significance = float(sig)
        except Exception:
            significance = 0.0
        out.append(QuestionCandidate(text=str(text), significance=significance))
    return out


def append_significant_questions(
    *,
    questions_payload: Any,
    open_questions_path: Path,
    threshold: float,
    run_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    candidates = _extract_candidates(questions_payload)
    selected = [q for q in candidates if q.significance >= threshold]

    if not selected:
        return {
            "status": "no_questions_above_threshold",
            "threshold": threshold,
            "run_id": run_id,
            "selected_count": 0,
        }

    open_questions_path.parent.mkdir(parents=True, exist_ok=True)
    if open_questions_path.exists():
        existing = open_questions_path.read_text(encoding="utf-8")
    else:
        existing = "# Open Questions\n\nThis document is append-only. Additions only; no edits to prior content.\n"
        if not dry_run:
            open_questions_path.write_text(existing, encoding="utf-8")

    style, next_idx = _next_index_style(existing)
    ts = _utc_now()
    commit_sha = _commit_sha()
    header = f"\n## Research Wanderer Session {ts} (run_id={run_id}, commit={commit_sha})\n"
    lines: list[str] = [header]
    for q in selected:
        text = _sanitize(q.text)
        if style == "roman":
            marker = _int_to_roman(next_idx)
        else:
            marker = str(next_idx)
        lines.append(f"{marker}. {text} [significance={q.significance:.3f}]\n")
        next_idx += 1
    append_block = "".join(lines)

    if not dry_run:
        with open_questions_path.open("a", encoding="utf-8") as f:
            f.write(append_block)

    try:
        target_path = str(open_questions_path.relative_to(REPO_ROOT))
    except Exception:
        target_path = str(open_questions_path)

    return {
        "status": "appended" if not dry_run else "dry_run",
        "threshold": threshold,
        "run_id": run_id,
        "commit_sha": commit_sha,
        "selected_count": len(selected),
        "append_preview": append_block,
        "target_path": target_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Research wanderer -> OPEN_QUESTIONS append pipeline")
    parser.add_argument("--input", help="Path to JSON payload containing question candidates")
    parser.add_argument("--question", action="append", default=[], help="Manual question (significance defaults to 1.0)")
    parser.add_argument("--threshold", type=float, default=float(os.environ.get("OPENCLAW_RESEARCH_Q_SIG_THRESHOLD", "0.80")))
    parser.add_argument("--run-id", default=os.environ.get("OPENCLAW_RUN_ID", uuid.uuid4().hex[:12]))
    parser.add_argument("--open-questions-path", default=str(DEFAULT_OPEN_QUESTIONS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload: Any = []
    if args.input:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.question:
        payload = list(payload) if isinstance(payload, list) else ([] if payload == [] else [payload])
        payload.extend({"question": q, "significance": 1.0} for q in args.question)

    result = append_significant_questions(
        questions_payload=payload,
        open_questions_path=Path(args.open_questions_path),
        threshold=float(args.threshold),
        run_id=str(args.run_id),
        dry_run=bool(args.dry_run),
    )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
