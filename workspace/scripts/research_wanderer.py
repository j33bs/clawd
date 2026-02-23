#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPEN_QUESTIONS = REPO_ROOT / "workspace" / "OPEN_QUESTIONS.md"
DEFAULT_WANDER_LOG = REPO_ROOT / "workspace" / "memory" / "wander_log.jsonl"

HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))
try:
    from hivemind.inquiry_momentum import compute_inquiry_momentum  # type: ignore
except Exception:  # pragma: no cover - optional fallback
    compute_inquiry_momentum = None  # type: ignore

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


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _inquiry_momentum(candidates: list[QuestionCandidate]) -> dict[str, float]:
    questions = [c.text for c in candidates]
    significance = [float(c.significance) for c in candidates]
    if callable(compute_inquiry_momentum):
        try:
            return dict(compute_inquiry_momentum(questions, significance_values=significance))
        except Exception:
            pass
    avg_sig = sum(significance) / len(significance) if significance else 0.0
    score = min(1.0, max(0.0, avg_sig))
    return {"score": round(score, 6), "avg_significance": round(avg_sig, 6), "question_count_score": 0.0, "token_diversity": 0.0}


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
    parser.add_argument("--session-id", default=os.environ.get("OPENCLAW_SESSION_ID", uuid.uuid4().hex[:16]))
    parser.add_argument("--trigger", default=os.environ.get("OPENCLAW_WANDER_TRIGGER", "manual"))
    parser.add_argument("--inquiry-threshold", type=float, default=float(os.environ.get("OPENCLAW_INQUIRY_MOMENTUM_THRESHOLD", "0.65")))
    parser.add_argument("--open-questions-path", default=str(DEFAULT_OPEN_QUESTIONS))
    parser.add_argument("--wander-log-path", default=str(Path(os.environ.get("OPENCLAW_WANDER_LOG_PATH", str(DEFAULT_WANDER_LOG)))))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    payload: Any = []
    if args.input:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.question:
        payload = list(payload) if isinstance(payload, list) else ([] if payload == [] else [payload])
        payload.extend({"question": q, "significance": 1.0} for q in args.question)

    candidates = _extract_candidates(payload)
    momentum = _inquiry_momentum(candidates)
    score = float(momentum.get("score", 0.0))
    result = append_significant_questions(
        questions_payload=payload,
        open_questions_path=Path(args.open_questions_path),
        threshold=float(args.threshold),
        run_id=str(args.run_id),
        dry_run=bool(args.dry_run),
    )
    duration_ms = int((time.perf_counter() - started) * 1000.0)
    log_row = {
        "timestamp": _utc_now(),
        "session_id": str(args.session_id),
        "run_id": str(args.run_id),
        "trigger": str(args.trigger or "unknown"),
        "inquiry_momentum_score": score,
        "threshold": float(args.inquiry_threshold),
        "exceeded": bool(score >= float(args.inquiry_threshold)),
        "duration_ms": duration_ms,
        "trails_written_count": 0,
        "errors": [],
    }
    try:
        _append_jsonl(Path(args.wander_log_path), log_row)
    except Exception as exc:
        warning = {
            "event": "wander_log_append_failed",
            "path": str(args.wander_log_path),
            "error": f"{type(exc).__name__}:{exc}",
        }
        print(json.dumps(warning, ensure_ascii=False), file=sys.stderr)
        result["wander_log_warning"] = warning
    result["inquiry_momentum"] = {
        "score": score,
        "threshold": float(args.inquiry_threshold),
        "exceeded": bool(score >= float(args.inquiry_threshold)),
    }
    result["session_id"] = str(args.session_id)
    result["trigger"] = str(args.trigger or "unknown")
    result["duration_ms"] = duration_ms

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
