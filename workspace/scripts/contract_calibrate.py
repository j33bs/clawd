#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTRACTCTL = ROOT / "workspace" / "scripts" / "contractctl.py"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def utc_stamp(value: dt.datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int((len(ordered) - 1) * p)
    return float(ordered[idx])


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sh(env: dict[str, str], *cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), cwd=str(ROOT), capture_output=True, text=True, env=env, check=False)


def parse_tick(proc: subprocess.CompletedProcess) -> dict[str, Any]:
    text = (proc.stdout or "").strip()
    if not text:
        return {"rc": proc.returncode}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"rc": proc.returncode, "raw": text}


def append_signal(path: Path, *, count: int, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = utc_stamp()
    with path.open("a", encoding="utf-8") as fh:
        for _ in range(max(0, count)):
            fh.write(json.dumps({"ts": ts, "kind": "service_request", "meta": {"source": source}}, sort_keys=True) + "\n")


def load_signal_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8").splitlines())


def run_phase(*, env: dict[str, str], state_dir: Path, phase: str, duration_s: int, tick_s: int, signal_burst: int) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    signal_path = state_dir / "signals" / "activity.jsonl"
    steps = max(1, duration_s // max(1, tick_s))
    for i in range(steps):
        if signal_burst > 0:
            append_signal(signal_path, count=signal_burst, source=f"calibration_{phase}")
        proc = sh(env, "python3", str(CONTRACTCTL), "tick")
        tick = parse_tick(proc)
        current = read_json(state_dir / "current.json", {})
        service_load = current.get("service_load") if isinstance(current, dict) else {}
        sample = {
            "phase": phase,
            "index": i,
            "ts": utc_stamp(),
            "mode": tick.get("mode") or current.get("mode"),
            "source": tick.get("source") or current.get("source"),
            "ewma_rate": tick.get("ewma_rate") if isinstance(tick.get("ewma_rate"), (int, float)) else service_load.get("ewma_rate"),
            "idle": bool(tick.get("idle") if "idle" in tick else service_load.get("idle")),
            "rate_per_min": service_load.get("rate_per_min"),
            "events_in_window": service_load.get("events"),
            "signal_count_total": load_signal_count(signal_path),
        }
        samples.append(sample)
        if i < steps - 1:
            time.sleep(max(1, tick_s))
    return samples


def configure_fast_policy(state_dir: Path) -> None:
    current_path = state_dir / "current.json"
    current = read_json(current_path, {})
    if not isinstance(current, dict):
        current = {}
    policy = current.get("policy") if isinstance(current.get("policy"), dict) else {}
    policy.update(
        {
            "window_minutes": int(os.environ.get("OPENCLAW_CAL_WINDOW_MIN", "2")),
            "min_mode_minutes": int(os.environ.get("OPENCLAW_CAL_MIN_MODE_MIN", "1")),
            "idle_window_seconds": int(os.environ.get("OPENCLAW_CAL_IDLE_WINDOW_S", "30")),
            "alpha": float(os.environ.get("OPENCLAW_CAL_ALPHA", "0.6")),
        }
    )
    current["policy"] = policy
    write_json(current_path, current)


def mode_flips(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flips: list[dict[str, Any]] = []
    prev = None
    for row in samples:
        mode = row.get("mode")
        if prev is None:
            prev = mode
            continue
        if mode != prev:
            flips.append({"ts": row.get("ts"), "from": prev, "to": mode, "phase": row.get("phase")})
            prev = mode
    return flips


def main() -> int:
    parser = argparse.ArgumentParser(description="Contract threshold calibration experiment")
    parser.add_argument("--state-dir", default=str(ROOT / "workspace" / "state_runtime" / "contract_calibration"))
    parser.add_argument("--active-seconds", type=int, default=36)
    parser.add_argument("--idle-seconds", type=int, default=48)
    parser.add_argument("--tick-seconds", type=int, default=6)
    parser.add_argument("--signal-burst", type=int, default=4)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    state_dir = Path(args.state_dir).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["OPENCLAW_CONTRACT_STATE_DIR"] = str(state_dir)

    sh(env, "python3", str(CONTRACTCTL), "tick")
    configure_fast_policy(state_dir)

    active = run_phase(
        env=env,
        state_dir=state_dir,
        phase="active",
        duration_s=max(6, args.active_seconds),
        tick_s=max(2, args.tick_seconds),
        signal_burst=max(1, args.signal_burst),
    )
    idle = run_phase(
        env=env,
        state_dir=state_dir,
        phase="idle",
        duration_s=max(6, args.idle_seconds),
        tick_s=max(2, args.tick_seconds),
        signal_burst=0,
    )
    samples = active + idle

    active_ewma = [float(s.get("ewma_rate")) for s in active if isinstance(s.get("ewma_rate"), (int, float))]
    idle_ewma = [float(s.get("ewma_rate")) for s in idle if isinstance(s.get("ewma_rate"), (int, float))]

    active_p50 = percentile(active_ewma, 0.50)
    active_p25 = percentile(active_ewma, 0.25)
    idle_p90 = percentile(idle_ewma, 0.90)
    high = round(max((active_p50 + idle_p90) / 2.0, idle_p90 * 1.4, 0.05), 3)
    low = round(max(idle_p90 * 1.1, min(high * 0.65, active_p25 * 0.5 if active_p25 > 0 else high * 0.5)), 3)
    if low >= high:
        low = round(max(0.01, high * 0.6), 3)

    first_idle_sample = next((s for s in idle if s.get("idle") is True), None)
    idle_window_reco = 30
    if first_idle_sample and isinstance(first_idle_sample.get("index"), int):
        idle_window_reco = max(20, int((first_idle_sample["index"] + 1) * max(2, args.tick_seconds)))

    report = {
        "ts": utc_stamp(),
        "state_dir": str(state_dir),
        "experiment": {
            "active_seconds": args.active_seconds,
            "idle_seconds": args.idle_seconds,
            "tick_seconds": args.tick_seconds,
            "signal_burst": args.signal_burst,
            "samples": len(samples),
        },
        "signals_total": load_signal_count(state_dir / "signals" / "activity.jsonl"),
        "mode_flips": mode_flips(samples),
        "active_ewma": {"p25": round(active_p25, 3), "p50": round(active_p50, 3)},
        "idle_ewma": {"p90": round(idle_p90, 3)},
        "recommendation": {
            "service_rate_high": high,
            "service_rate_low": low,
            "idle_window_seconds": idle_window_reco,
        },
        "samples": samples,
    }

    output_path = Path(args.output).resolve() if args.output else None
    if output_path:
        write_json(output_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
