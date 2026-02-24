"""Run CorrespondenceStore gates via the canonical gates.run_all_gates()."""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WORKSPACE, "store"))

from gates import run_all_gates
from sync import DEFAULT_MODEL

RESULTS_PATH = os.path.join(WORKSPACE, "store", "poc_results.json")


def main() -> int:
    results = run_all_gates()

    serializable = {
        "timestamp": datetime.now().isoformat(),
        "model": DEFAULT_MODEL,
        "all_passed": results["all_passed"],
        "gates": {str(k): v for k, v in results["gates"].items()},
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, default=str)

    print(f"\nResults saved to: workspace/store/poc_results.json")
    return 0 if results["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
