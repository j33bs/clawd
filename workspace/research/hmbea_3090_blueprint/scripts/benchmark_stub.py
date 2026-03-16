from __future__ import annotations

import json
from pathlib import Path
from statistics import mean


def main() -> None:
    path = Path("results.jsonl")
    if not path.exists():
        raise SystemExit("Place a results.jsonl file in the working directory.")

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    success = [1 if row.get("success") else 0 for row in rows]
    latency = [float(row.get("latency_s", 0.0)) for row in rows]
    escalation = [1 if row.get("escalated") else 0 for row in rows]

    report = {
        "n": len(rows),
        "success_rate": mean(success) if rows else 0.0,
        "avg_latency_s": mean(latency) if rows else 0.0,
        "escalation_rate": mean(escalation) if rows else 0.0,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
