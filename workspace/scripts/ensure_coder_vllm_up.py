#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from contract_policy import gpu_tool_allowed_now, load_contract  # type: ignore  # noqa: E402

CONTRACT_PATH = Path(
    os.environ.get("OPENCLAW_CONTRACT_CURRENT")
    or (ROOT / "workspace" / "state_runtime" / "contract" / "current.json")
)
GPU_LOCK = ROOT / "workspace" / "scripts" / "gpu_lock.py"
UNIT = "openclaw-tool-coder-vllm-models.service"
HOST = "127.0.0.1"
PORT = 8002


def tcp_ready(timeout_s: int = 25) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        try:
            sock.connect((HOST, PORT))
            return True
        except Exception:
            time.sleep(0.5)
        finally:
            try:
                sock.close()
            except Exception:
                pass
    return False


def run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def out(payload: dict, rc: int) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return rc


def main() -> int:
    contract = load_contract(str(CONTRACT_PATH))
    policy = gpu_tool_allowed_now("coder_vllm.models", contract)
    if not bool(policy.get("allowed")):
        return out(
            {
                "ok": False,
                "offline_class": "POLICY",
                "reason": policy.get("reason"),
                "mode": policy.get("mode"),
            },
            2,
        )

    # If already up, no start needed.
    if tcp_ready(timeout_s=1):
        return out({"ok": True, "started": False, "port": PORT}, 0)

    claim = run([str(GPU_LOCK), "claim", "--holder", "coder_vllm.models", "--reason", "ensure_up", "--ttl-minutes", "30"])
    if claim.returncode != 0:
        return out(
            {
                "ok": False,
                "offline_class": "POLICY",
                "reason": "gpu_lock_held",
                "detail": (claim.stdout or claim.stderr).strip(),
            },
            3,
        )

    run(["systemctl", "--user", "reset-failed", UNIT])
    run(["systemctl", "--user", "start", UNIT])

    if tcp_ready(timeout_s=25):
        return out({"ok": True, "started": True, "port": PORT}, 0)

    run([str(GPU_LOCK), "release", "--holder", "coder_vllm.models"])
    return out(
        {
            "ok": False,
            "offline_class": "FAULT",
            "reason": "start_failed_or_vram_gate",
            "hint": "check journalctl --user -u openclaw-tool-coder-vllm-models.service",
        },
        4,
    )


if __name__ == "__main__":
    raise SystemExit(main())
