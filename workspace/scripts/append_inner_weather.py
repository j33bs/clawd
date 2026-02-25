#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO_ROOT / "workspace" / "inner_weather.md"
TOKEN_RE = re.compile(r"\b[A-Za-z0-9_-]{24,}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _sanitize(note: str) -> str:
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", note)
    text = TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    return " ".join(text.split())


def append_inner_weather(note: str, node: str, path: Path) -> dict:
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    line = f"## {ts} [{node}]\n- { _sanitize(note) }\n\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    return {"status": "appended", "path": str(path.relative_to(REPO_ROOT)), "timestamp": ts, "node": node}


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a manual inner-weather note")
    parser.add_argument("--note", required=True)
    parser.add_argument("--node", default=os.environ.get("OPENCLAW_NODE_ID", "Dali/C_Lawd"))
    parser.add_argument("--path", default=str(DEFAULT_PATH))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = append_inner_weather(args.note, args.node, Path(args.path))
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"appended inner weather note at {result['timestamp']} -> {result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
