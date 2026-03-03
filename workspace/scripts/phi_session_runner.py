#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))


@dataclass
class SessionResult:
    status: str
    phi_value: float | None
    method_ref: str
    notes: str
    snapshot_path: str
    commit_sha: str
    date_utc: str
    node: str


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _commit_sha() -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True)
        .strip()
    )


def _detect_node() -> str:
    return os.environ.get("OPENCLAW_NODE_ID", "Dali/C_Lawd")


def _module_statuses() -> dict[str, Any]:
    from hivemind.dynamics_pipeline import TactiDynamicsPipeline  # type: ignore

    pipeline = TactiDynamicsPipeline(agent_ids=["main", "codex", "claude"], seed=23)
    snap = pipeline.snapshot()
    flags = snap.get("flags", {})
    return {
        "flags": flags,
        "modules": {
            "peer_graph": "active" if flags.get("ENABLE_MURMURATION") else "wired_but_passive",
            "reservoir": "active" if flags.get("ENABLE_RESERVOIR") else "wired_but_passive",
            "physarum_router": "active" if flags.get("ENABLE_PHYSARUM_ROUTER") else "wired_but_passive",
            "trail_memory": "active" if flags.get("ENABLE_TRAIL_MEMORY") else "wired_but_passive",
            "active_inference": "active" if flags.get("OPENCLAW_COUNTERFACTUAL_REPLAY") else "wired_but_passive",
        },
        "seed": 23,
    }


def _write_snapshot(ts_compact: str, payload: dict[str, Any]) -> Path:
    out_dir = REPO_ROOT / "workspace" / "phi_sessions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ts_compact}_wiring_snapshot.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def _try_existing_phi_calculator(snapshot_payload: dict[str, Any]) -> tuple[str, float | None, str]:
    candidates = [
        "workspace.tacti.phi_integration",
        "workspace.tacti_cr.phi_integration",
        "hivemind.phi",
        "hivemind.integrated_information",
    ]
    for module_name in candidates:
        try:
            mod = importlib.import_module(module_name)
        except Exception:
            continue
        for fn_name in ("compute_phi", "calculate_phi", "run_phi"):
            fn = getattr(mod, fn_name, None)
            if callable(fn):
                value = fn(snapshot_payload)
                return "ok", float(value), f"{module_name}.{fn_name}"
    return "blocked", None, "AIN_PHI_CALCULATOR_MISSING"


def run_session(*, dry_run: bool = False) -> SessionResult:
    date_utc = _utc_now()
    ts_compact = date_utc.replace("-", "").replace(":", "")
    commit_sha = _commit_sha()
    node = _detect_node()
    host = socket.gethostname()

    wiring = _module_statuses()
    snapshot_payload = {
        "date_utc": date_utc,
        "commit_sha": commit_sha,
        "node": node,
        "host": host,
        "dataset_version": "hivemind_wiring_snapshot_v1",
        "wiring": wiring,
    }
    if dry_run:
        snapshot_ref = "DRY_RUN::workspace/phi_sessions/<timestamp>_wiring_snapshot.json"
    else:
        snapshot_path = _write_snapshot(ts_compact, snapshot_payload)
        snapshot_ref = str(snapshot_path.relative_to(REPO_ROOT))

    status, phi_value, method_ref = _try_existing_phi_calculator(snapshot_payload)
    if status == "ok":
        notes = "AIN Φ computed with existing calculator entrypoint"
    else:
        notes = "Blocked: no canonical AIN Φ calculator entrypoint found; session artifact captured"

    return SessionResult(
        status=status,
        phi_value=phi_value,
        method_ref=method_ref,
        notes=notes,
        snapshot_path=snapshot_ref,
        commit_sha=commit_sha,
        date_utc=date_utc,
        node=node,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one deterministic AIN Φ measurement session")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--dry-run", action="store_true", help="compute deterministically without writing files")
    args = parser.parse_args()

    result = run_session(dry_run=args.dry_run)
    payload = {
        "status": result.status,
        "date_utc": result.date_utc,
        "commit_sha": result.commit_sha,
        "node": result.node,
        "wiring_snapshot_ref": result.snapshot_path,
        "phi_value": result.phi_value,
        "method_ref": result.method_ref,
        "notes": result.notes,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))

    if result.status != "ok":
        print(
            "ERROR: AIN Φ calculator missing. Session captured as blocked; see method_ref and notes.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
