from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_json, load_json, utc_now_iso
from .paths import RUNTIME_ROOT, ensure_runtime_dirs


class ControlBus:
    def __init__(self, *, state_path: Path | None = None):
        ensure_runtime_dirs()
        self.state_path = state_path or (RUNTIME_ROOT / "control_bus_state.json")
        self._lock = threading.Lock()
        self._transient: dict[str, dict[str, float]] = {}
        self._persistent: dict[str, Any] = {}
        self._load_state()

    def _load_state(self) -> None:
        payload = load_json(self.state_path, {})
        if not isinstance(payload, dict):
            return
        persistent = payload.get("persistent")
        if isinstance(persistent, dict):
            self._persistent = dict(persistent)

    def _prune_locked(self, now: float) -> None:
        expired = [name for name, row in self._transient.items() if float(row.get("expires_at", 0.0)) <= now]
        for name in expired:
            self._transient.pop(name, None)

    def _persist_locked(self) -> None:
        now = time.monotonic()
        now_epoch = time.time()
        active_transient = {
            key: {
                "value": float(row.get("value", 0.0)),
                "ttl_s": max(0.0, float(row.get("expires_at", now) - now)),
                "expires_at_epoch": max(0.0, float(row.get("expires_at_epoch", now_epoch))),
            }
            for key, row in self._transient.items()
        }
        atomic_write_json(
            self.state_path,
            {
                "ts": utc_now_iso(),
                "persistent": dict(self._persistent),
                "active_transient": active_transient,
            },
        )

    def set_transient(self, *, name: str, value: float, ttl_seconds: float) -> None:
        ttl = max(0.0, float(ttl_seconds))
        with self._lock:
            now = time.monotonic()
            now_epoch = time.time()
            self._prune_locked(now)
            self._transient[str(name)] = {
                "value": float(value),
                "expires_at": now + ttl,
                "expires_at_epoch": now_epoch + ttl,
            }
            self._persist_locked()

    def set_transients(self, controls: dict[str, float], *, ttl_seconds: float) -> None:
        ttl = max(0.0, float(ttl_seconds))
        with self._lock:
            now = time.monotonic()
            now_epoch = time.time()
            self._prune_locked(now)
            expires_at = now + ttl
            expires_at_epoch = now_epoch + ttl
            for key, value in controls.items():
                self._transient[str(key)] = {
                    "value": float(value),
                    "expires_at": expires_at,
                    "expires_at_epoch": expires_at_epoch,
                }
            self._persist_locked()

    def clear_transient(self, name: str) -> None:
        with self._lock:
            self._transient.pop(str(name), None)
            self._persist_locked()

    def set_persistent(self, *, key: str, value: Any) -> None:
        with self._lock:
            self._persistent[str(key)] = value
            self._persist_locked()

    def persistent(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._persistent)

    def active_transient(self) -> dict[str, dict[str, float]]:
        with self._lock:
            now = time.monotonic()
            self._prune_locked(now)
            return {
                key: {
                    "value": float(row.get("value", 0.0)),
                    "ttl_s": max(0.0, float(row.get("expires_at", now) - now)),
                }
                for key, row in self._transient.items()
            }

    def get_value(self, name: str, default: float = 0.0) -> float:
        with self._lock:
            now = time.monotonic()
            self._prune_locked(now)
            row = self._transient.get(str(name))
            if not isinstance(row, dict):
                return float(default)
            return float(row.get("value", default))
