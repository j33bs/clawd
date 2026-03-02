#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "workspace" / "state_runtime" / "contract" / "current.json"


def _parse_z(value: Any) -> dt.datetime | None:
    s = str(value or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def load_contract(path: str | None = None) -> dict[str, Any]:
    chosen = Path(path or os.environ.get("OPENCLAW_CONTRACT_CURRENT") or DEFAULT_CONTRACT)
    if not chosen.exists():
        return {}
    try:
        data = json.loads(chosen.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def contract_allows_code(contract: dict[str, Any]) -> bool:
    return str(contract.get("mode", "")).upper() == "CODE"


def contract_forces_code_override(contract: dict[str, Any]) -> bool:
    override = contract.get("override")
    if not isinstance(override, dict):
        return False
    if str(override.get("mode", "")).upper() != "CODE":
        return False

    ttl_raw = override.get("ttl_until")
    if ttl_raw is None:
        return True

    ttl = _parse_z(ttl_raw)
    if ttl is None:
        return False
    return dt.datetime.now(dt.timezone.utc) < ttl


def gpu_tool_allowed_now(tool_id: str, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    cur = contract if isinstance(contract, dict) else load_contract()
    mode = str(cur.get("mode", "")).upper() or None
    source = cur.get("source")
    if contract_allows_code(cur):
        return {
            "tool_id": tool_id,
            "allowed": True,
            "reason": "mode_code",
            "mode": mode,
            "source": source,
        }
    if contract_forces_code_override(cur):
        return {
            "tool_id": tool_id,
            "allowed": True,
            "reason": "forced_code_override",
            "mode": mode,
            "source": source,
        }
    return {
        "tool_id": tool_id,
        "allowed": False,
        "reason": "policy_service_or_idle",
        "mode": mode,
        "source": source,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Contract policy helpers")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("gpu-allowed", help="Check whether a GPU tool may run now")
    p.add_argument("--tool-id", required=True)
    p.add_argument("--contract", default="")

    args = parser.parse_args()

    if args.cmd == "gpu-allowed":
        payload = gpu_tool_allowed_now(args.tool_id, load_contract(args.contract or None))
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
