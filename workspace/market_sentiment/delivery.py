from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


@dataclass(frozen=True)
class DeliveryResult:
    mode: str
    status: str
    target: str
    detail: str = ""


def deliver_snapshot(local_path: Path, config: dict[str, Any]) -> DeliveryResult:
    delivery_cfg = dict(config.get("delivery") or {})
    if not delivery_cfg.get("enabled"):
        return DeliveryResult(mode="disabled", status="skipped", target=str(local_path))

    mode = str(delivery_cfg.get("mode") or "").strip()
    if mode != "ssh_push":
        raise ValueError(f"unsupported_delivery_mode:{mode or 'missing'}")
    return _deliver_via_ssh_push(Path(local_path), delivery_cfg)


def _deliver_via_ssh_push(local_path: Path, delivery_cfg: dict[str, Any]) -> DeliveryResult:
    host = str(delivery_cfg.get("host") or "").strip()
    user = str(delivery_cfg.get("user") or "").strip()
    remote_path_raw = str(delivery_cfg.get("remote_path") or "").strip()
    timeout_seconds = int(delivery_cfg.get("timeout_seconds") or 15)
    connect_timeout = int(delivery_cfg.get("connect_timeout_seconds") or min(timeout_seconds, 5))
    disable_ssh_config = bool(delivery_cfg.get("disable_ssh_config", False))
    if not host:
        raise ValueError("delivery_host_missing")
    if not remote_path_raw.startswith("/"):
        raise ValueError("delivery_remote_path_invalid")

    payload = Path(local_path).read_bytes()
    remote_path = PurePosixPath(remote_path_raw)
    remote_dir = remote_path.parent
    remote_tmp = PurePosixPath(f"{remote_path_raw}.tmp.{os.getpid()}")
    remote_command = (
        f"mkdir -p {shlex.quote(str(remote_dir))} && "
        f"cat > {shlex.quote(str(remote_tmp))} && "
        f"mv {shlex.quote(str(remote_tmp))} {shlex.quote(str(remote_path))}"
    )
    target = f"{user}@{host}" if user else host
    command = ["ssh"]
    if disable_ssh_config:
        command.extend(["-F", "/dev/null"])
    command.extend(
        [
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={connect_timeout}",
            target,
            remote_command,
        ]
    )
    completed = subprocess.run(
        command,
        input=payload,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        detail = stderr or f"ssh_exit_{completed.returncode}"
        raise RuntimeError(f"delivery_ssh_push_failed:{detail}")
    return DeliveryResult(
        mode="ssh_push",
        status="ok",
        target=f"{target}:{remote_path_raw}",
        detail=f"bytes={len(payload)}",
    )
