from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any

from .io_utils import utc_now_iso
from .paths import GPU_LEASE_PATH, ensure_runtime_dirs


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class GPULease:
    def __init__(self, *, path: Path = GPU_LEASE_PATH):
        ensure_runtime_dirs()
        self.path = path
        self.last_error = ""

    def _now(self) -> float:
        return float(time.time())

    def _lease_valid(self, payload: dict[str, Any], now: float) -> bool:
        expiry = float(payload.get("expiry_ts", 0.0) or 0.0)
        return expiry > now

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except Exception:
            return False
        return True

    def _pid_cmdline(self, pid: int) -> str:
        if pid <= 0:
            return ""
        try:
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        except Exception:
            return ""
        parts = [item.decode("utf-8", errors="ignore") for item in raw.split(b"\0") if item]
        return " ".join(part.strip() for part in parts if part.strip())

    def _owner_matches_process(self, owner: str, pid: int) -> bool:
        owner_text = str(owner or "").strip().lower()
        cmdline = self._pid_cmdline(pid).lower()
        if not owner_text or not cmdline:
            return True
        if owner_text.startswith("dali-fishtank:"):
            return ("cathedral.runtime" in cmdline) or ("dali_fishtank_start.sh" in cmdline)
        return True

    def current(self) -> dict[str, Any]:
        return _read_json(self.path)

    def acquire(self, *, owner: str, mode: str, ttl_s: float, policy: str = "exclusive") -> bool:
        now = self._now()
        ttl = max(2.0, float(ttl_s))
        incoming_policy = str(policy or "exclusive").strip().lower()
        if incoming_policy not in {"exclusive", "shared"}:
            incoming_policy = "exclusive"

        existing = self.current()
        holders = [str(item) for item in existing.get("holders", []) if str(item).strip()]
        if not holders and str(existing.get("owner", "")).strip():
            holders = [str(existing.get("owner"))]
        valid = self._lease_valid(existing, now)
        if valid:
            host = str(existing.get("host", "") or "")
            pid = int(existing.get("pid", 0) or 0)
            if host == socket.gethostname() and pid > 0 and not self._pid_alive(pid):
                valid = False
            elif host == socket.gethostname() and pid > 0 and not self._owner_matches_process(str(existing.get("owner", "") or ""), pid):
                valid = False
        if valid and owner not in holders:
            existing_policy = str(existing.get("policy", "exclusive") or "exclusive").strip().lower()
            shared_ok = incoming_policy == "shared" or existing_policy == "shared" or bool(existing.get("shared", False))
            if not shared_ok:
                self.last_error = (
                    f"lease_held owner={existing.get('owner','unknown')} "
                    f"expiry_ts={existing.get('expiry_ts', 0)} policy={existing_policy}"
                )
                return False
            holders.append(owner)
        elif not valid:
            holders = [owner]
        elif owner not in holders:
            holders.append(owner)

        shared = len(holders) > 1 or incoming_policy == "shared"
        payload = {
            "ts": utc_now_iso(),
            "owner": holders[0],
            "holders": holders,
            "mode": str(mode or "exclusive"),
            "policy": ("shared" if shared else "exclusive"),
            "shared": bool(shared),
            "pid": int(os.getpid()),
            "host": socket.gethostname(),
            "start_ts": existing.get("start_ts", utc_now_iso()) if valid else utc_now_iso(),
            "expiry_ts": now + ttl,
        }
        _atomic_write_json(self.path, payload)
        self.last_error = ""
        return True

    def renew(self, *, owner: str, ttl_s: float) -> bool:
        now = self._now()
        ttl = max(2.0, float(ttl_s))
        existing = self.current()
        if not existing:
            self.last_error = "lease_missing"
            return False
        holders = [str(item) for item in existing.get("holders", []) if str(item).strip()]
        if not holders and str(existing.get("owner", "")).strip():
            holders = [str(existing.get("owner"))]
        if owner not in holders:
            self.last_error = f"owner_not_holder owner={owner}"
            return False
        existing["ts"] = utc_now_iso()
        existing["expiry_ts"] = now + ttl
        existing["owner"] = holders[0]
        existing["holders"] = holders
        existing["shared"] = len(holders) > 1
        existing["policy"] = "shared" if len(holders) > 1 else str(existing.get("policy", "exclusive") or "exclusive")
        _atomic_write_json(self.path, existing)
        self.last_error = ""
        return True

    def release(self, *, owner: str) -> bool:
        existing = self.current()
        if not existing:
            return True
        holders = [str(item) for item in existing.get("holders", []) if str(item).strip()]
        if not holders and str(existing.get("owner", "")).strip():
            holders = [str(existing.get("owner"))]
        if owner in holders:
            holders = [item for item in holders if item != owner]
        if not holders:
            try:
                self.path.unlink(missing_ok=True)
            except Exception:
                return False
            return True
        existing["ts"] = utc_now_iso()
        existing["owner"] = holders[0]
        existing["holders"] = holders
        existing["shared"] = len(holders) > 1
        existing["policy"] = "shared" if len(holders) > 1 else "exclusive"
        _atomic_write_json(self.path, existing)
        return True
