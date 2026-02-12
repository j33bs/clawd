#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def validate(payload: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["evidence must be a JSON object"]

    gate_result = payload.get("gate_result")
    if gate_result not in {"pass", "fail"}:
        errors.append("gate_result must be one of: pass, fail")

    completion_rate = payload.get("completion_rate")
    if not isinstance(completion_rate, (int, float)) or isinstance(completion_rate, bool):
        errors.append("completion_rate must be numeric")
    else:
        if math.isnan(float(completion_rate)) or float(completion_rate) < 0.0 or float(completion_rate) > 1.0:
            errors.append("completion_rate must be within [0, 1]")

    traces = payload.get("traces")
    if not isinstance(traces, int) or isinstance(traces, bool):
        errors.append("traces must be an integer")
    elif traces < 0:
        errors.append("traces must be >= 0")

    smoke = payload.get("smoke_log_truncated")
    if not isinstance(smoke, bool):
        errors.append("smoke_log_truncated must be a boolean")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate canonical System-1 evidence keys.")
    parser.add_argument("evidence_path", help="Path to evidence JSON file.")
    parser.add_argument(
        "--summary-out",
        default="",
        help="Optional file path for a short human-readable summary.",
    )
    args = parser.parse_args()

    evidence_path = Path(args.evidence_path)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    errors = validate(payload)
    if errors:
        for err in errors:
            print(f"FAIL: {err}")
        return 1

    summary = (
        f"gate_result={payload['gate_result']}\n"
        f"completion_rate={payload['completion_rate']}\n"
        f"traces={payload['traces']}\n"
        f"smoke_log_truncated={str(payload['smoke_log_truncated']).lower()}\n"
    )
    print(summary, end="")
    if args.summary_out:
        out_path = Path(args.summary_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(summary, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
