#!/usr/bin/env python3
"""VRAM guard for coder vLLM lane startup."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from event_envelope import append_envelope, make_envelope


DEFAULT_MIN_FREE_MB = 7000


def _env_bool(name: str, fallback: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(fallback)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def parse_nvidia_smi_csv(text: str) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    for line in str(text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        parts = [item.strip() for item in s.split(",")]
        if len(parts) < 2:
            continue
        total = int(parts[0])
        used = int(parts[1])
        free = total - used
        rows.append({"total_mb": total, "used_mb": used, "free_mb": free})
    return rows


def evaluate_vram_guard(
    *,
    min_free_mb: int = DEFAULT_MIN_FREE_MB,
    allow_no_nvidia_smi: bool = False,
) -> dict[str, Any]:
    cmd = ["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"]
    base: dict[str, Any] = {
        "ok": False,
        "reason": "UNKNOWN",
        "message": "",
        "threshold_mb": int(min_free_mb),
        "gpu_count": 0,
        "max_free_vram_mb": None,
    }
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5)
    except FileNotFoundError:
        if allow_no_nvidia_smi:
            base.update(
                {
                    "ok": True,
                    "reason": "NO_NVIDIA_SMI_ALLOWED",
                    "message": "nvidia-smi missing; allowed by VLLM_CODER_ALLOW_NO_NVIDIA_SMI=true",
                }
            )
            return base
        base.update(
            {
                "ok": False,
                "reason": "NVIDIA_SMI_MISSING",
                "message": "nvidia-smi not found",
            }
        )
        return base
    except Exception as exc:
        base.update(
            {
                "ok": False,
                "reason": "NVIDIA_SMI_ERROR",
                "message": f"nvidia-smi execution failed: {type(exc).__name__}:{exc}",
            }
        )
        return base

    if cp.returncode != 0:
        base.update(
            {
                "ok": False,
                "reason": "NVIDIA_SMI_ERROR",
                "message": (cp.stderr or cp.stdout or "nvidia-smi failed").strip()[:240],
            }
        )
        return base

    try:
        rows = parse_nvidia_smi_csv(cp.stdout)
    except Exception as exc:
        base.update(
            {
                "ok": False,
                "reason": "NVIDIA_SMI_PARSE_ERROR",
                "message": f"unable to parse nvidia-smi output: {type(exc).__name__}:{exc}",
            }
        )
        return base

    if not rows:
        base.update(
            {
                "ok": False,
                "reason": "NVIDIA_SMI_PARSE_ERROR",
                "message": "no GPU rows parsed from nvidia-smi output",
            }
        )
        return base

    max_free = max(row["free_mb"] for row in rows)
    base.update({"gpu_count": len(rows), "max_free_vram_mb": int(max_free)})

    if max_free < int(min_free_mb):
        base.update(
            {
                "ok": False,
                "reason": "VRAM_LOW",
                "message": f"max free VRAM {max_free}MB is below threshold {int(min_free_mb)}MB",
            }
        )
        return base

    base.update(
        {
            "ok": True,
            "reason": "OK",
            "message": f"max free VRAM {max_free}MB meets threshold {int(min_free_mb)}MB",
        }
    )
    return base


def envelope_log_path() -> Path:
    raw = os.environ.get("OPENCLAW_EVENT_ENVELOPE_LOG_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "share" / "openclaw" / "events" / "gate_health.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Coder lane VRAM guard")
    parser.add_argument("--json", action="store_true", help="print JSON result (default)")
    args = parser.parse_args()

    threshold = int(os.environ.get("VLLM_CODER_MIN_FREE_VRAM_MB", str(DEFAULT_MIN_FREE_MB)) or DEFAULT_MIN_FREE_MB)
    allow_no = _env_bool("VLLM_CODER_ALLOW_NO_NVIDIA_SMI", False)
    verdict = evaluate_vram_guard(min_free_mb=threshold, allow_no_nvidia_smi=allow_no)

    # Default to machine-readable JSON output.
    _ = args
    print(json.dumps(verdict, ensure_ascii=False))
    env = make_envelope(
        event="vram_guard_verdict",
        severity=("INFO" if verdict.get("ok") else "WARN"),
        component="vram_guard",
        corr_id=os.environ.get("OPENCLAW_CANARY_CORR_ID", ""),
        details={
            "ok": bool(verdict.get("ok")),
            "reason": str(verdict.get("reason", "")),
            "threshold_mb": int(verdict.get("threshold_mb") or threshold),
            "max_free_vram_mb": verdict.get("max_free_vram_mb"),
            "gpu_count": int(verdict.get("gpu_count") or 0),
        },
    )
    append_envelope(envelope_log_path(), env)
    return 0 if verdict.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
