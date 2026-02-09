from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "reports" / "baseline_sim_metrics.json"

LINE_RE = re.compile(
    r"\[(SIM_[AB])\].*equity=\$([0-9.]+).*pnl=([-0-9.]+)%.*dd=([0-9.]+)%.*trades=([0-9]+) new, ([0-9]+) total"
)


def run_sim(sim_id: str) -> Dict[str, Any]:
    cmd = ["python3", "scripts/sim_runner.py", "--sim", sim_id]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m = None
    for line in out.splitlines():
        m = LINE_RE.search(line)
        if m:
            break
    if not m:
        print(f"FAIL: could not parse headline for {sim_id}.")
        print("--- output tail ---")
        print("\n".join(out.splitlines()[-10:]))
        sys.exit(1)

    return {
        "equity": float(m.group(2)),
        "pnl_pct": float(m.group(3)),
        "dd_pct": float(m.group(4)),
        "trades_new": int(m.group(5)),
        "trades_total": int(m.group(6)),
    }


def within_tol(val: float, base: float, tol: float) -> bool:
    return abs(val - base) <= tol


def main() -> int:
    if not BASELINE_PATH.exists():
        print(f"FAIL: baseline missing at {BASELINE_PATH}")
        return 1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    tol = baseline["tolerance"]

    results = {}
    for sim_id in ("SIM_A", "SIM_B"):
        results[sim_id] = run_sim(sim_id)

    failed = False
    for sim_id, observed in results.items():
        base = baseline[sim_id]
        checks = {
            "equity": within_tol(observed["equity"], base["equity"], tol["equity_abs"]),
            "pnl_pct": within_tol(observed["pnl_pct"], base["pnl_pct"], tol["pnl_pct_abs"]),
            "dd_pct": within_tol(observed["dd_pct"], base["dd_pct"], tol["dd_pct_abs"]),
            "trades_new": within_tol(observed["trades_new"], base["trades_new"], tol["trades_new_abs"]),
            "trades_total": within_tol(observed["trades_total"], base["trades_total"], tol["trades_total_abs"]),
        }
        if not all(checks.values()):
            failed = True
            print(f"FAIL: {sim_id} deviates from baseline")
            print(f"  baseline: {base}")
            print(f"  observed: {observed}")
            deltas = {k: (observed[k] - base[k]) for k in base}
            print(f"  deltas: {deltas}")
        else:
            print(f"PASS: {sim_id} matches baseline")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
