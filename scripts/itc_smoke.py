#!/usr/bin/env python3

import json
import tempfile
import time
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core_infra.econ_log import append_jsonl
from scripts.sim_runner import compute_sim_b_tilt
from workspace.itc.api import get_itc_signal
from workspace.itc.ingest.interfaces import FileDropAdapter, ingest_with_adapter


def main() -> int:
    run_id = f"itc_smoke_{int(time.time())}"
    with tempfile.TemporaryDirectory(prefix="openclaw_itc_smoke_") as tmp:
        root = Path(tmp)
        artifacts = root / "workspace" / "artifacts" / "itc"
        inbox = root / "workspace" / "data" / "itc" / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)

        fixture = {
            "source": "file",
            "ts_utc": "2026-02-18T12:00:00Z",
            "window": "4h",
            "metrics": {
                "sentiment": 0.4,
                "confidence": 0.85,
                "regime": "risk_on",
                "risk_on": 0.7,
                "risk_off": 0.3,
            },
        }
        drop = inbox / "signal.json"
        drop.write_text(json.dumps(fixture), encoding="utf-8")

        ingest_out = ingest_with_adapter(
            FileDropAdapter(inbox_dir=inbox, input_file=drop),
            run_id=run_id,
            artifact_root=artifacts,
        )

        selected = get_itc_signal(
            ts_utc="2026-02-18T12:30:00Z",
            lookback="8h",
            policy={"artifacts_root": str(artifacts), "run_id": run_id},
        )
        if selected.get("reason") != "ok":
            print(f"SMOKE_FAIL reason={selected.get('reason')}")
            return 2

        sent = float(selected["signal"]["metrics"].get("sentiment", 0.0))
        tilt = compute_sim_b_tilt(sent)

        econ = root / "economics" / "observe.jsonl"
        append_jsonl(
            str(econ),
            {
                "ts": "2026-02-18T12:30:00Z",
                "sim": "SIM_B",
                "type": "sim_b_tilt_applied",
                "payload": {
                    "sentiment": sent,
                    "tilt": tilt,
                    "reason": selected["reason"],
                    "source": selected["signal"].get("source"),
                },
            },
        )

        print("SMOKE_OK")
        print(f"run_id={run_id}")
        print(f"raw_path={ingest_out['paths']['raw_path']}")
        print(f"normalized_path={ingest_out['paths']['normalized_path']}")
        print(f"events_path={artifacts / 'events' / 'itc_events.jsonl'}")
        print(f"econ_log={econ}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
