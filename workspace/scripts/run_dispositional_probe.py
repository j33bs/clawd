#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBES_PATH = REPO_ROOT / "workspace" / "probes" / "dispositional_probes.md"
LOG_PATH = REPO_ROOT / "workspace" / "probes" / "dispositional_log.jsonl"


def _load_questions(path: Path) -> list[str]:
    questions: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line[0].isdigit() and ". " in line:
            questions.append(line.split(". ", 1)[1])
    return questions


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 12-question dispositional probe")
    parser.add_argument("--session-id", default=uuid.uuid4().hex[:12])
    parser.add_argument("--node", default=os.environ.get("OPENCLAW_NODE_ID", "Dali/C_Lawd"))
    parser.add_argument("--responses-json", help="Path to JSON array of responses")
    parser.add_argument("--response", action="append", default=[], help="Response in order; can repeat")
    parser.add_argument(
        "--session-start",
        action="store_true",
        help="Optional marker indicating this run was triggered at session start",
    )
    parser.add_argument("--log-path", default=str(LOG_PATH))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    questions = _load_questions(PROBES_PATH)
    if len(questions) != 12:
        raise SystemExit(f"expected 12 probe questions, found {len(questions)}")

    responses: list[str] = []
    if args.responses_json:
        loaded = json.loads(Path(args.responses_json).read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            responses = [str(x) for x in loaded]
    if args.response:
        responses = [str(x) for x in args.response]
    while len(responses) < len(questions):
        responses.append("")

    timestamp = _utc_now()
    payload = {
        "timestamp_utc": timestamp,
        "node": args.node,
        "session_id": args.session_id,
        "session_start": bool(args.session_start),
        "responses": [
            {"index": i + 1, "question": q, "response": responses[i]}
            for i, q in enumerate(questions)
        ],
    }

    out_path = Path(args.log_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    for i, q in enumerate(questions, start=1):
        print(f"{i}. {q}")

    if args.json:
        print(json.dumps({"status": "logged", "log_path": str(out_path.relative_to(REPO_ROOT)), "session_id": args.session_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
