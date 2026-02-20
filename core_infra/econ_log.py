from __future__ import annotations

import atexit
import json
import os
import threading
import time
from typing import Any, Dict

_FSYNC_BATCH_SIZE = 50
_FSYNC_INTERVAL_SECONDS = 0.5
_FSYNC_STATE_LOCK = threading.Lock()
_FSYNC_STATE: Dict[str, Dict[str, Any]] = {}


def _touch_state(path: str) -> Dict[str, Any]:
    state = _FSYNC_STATE.get(path)
    if state is None:
        state = {"pending": 0, "last_sync": time.monotonic()}
        _FSYNC_STATE[path] = state
    return state


def flush_pending(path: str | None = None) -> None:
    targets = []
    with _FSYNC_STATE_LOCK:
        if path is not None:
            state = _FSYNC_STATE.get(path)
            if state is not None:
                targets.append((path, state))
        else:
            targets = list(_FSYNC_STATE.items())
    for target_path, state in targets:
        pending = int(state.get("pending", 0))
        if pending <= 0:
            continue
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        try:
            with open(target_path, "a", encoding="utf-8") as f:
                f.flush()
                os.fsync(f.fileno())
        finally:
            with _FSYNC_STATE_LOCK:
                current = _FSYNC_STATE.get(target_path)
                if current is not None:
                    current["pending"] = 0.0
                    current["last_sync"] = time.monotonic()


def _flush_all_pending() -> None:
    flush_pending(None)


atexit.register(_flush_all_pending)


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        now = time.monotonic()
        with _FSYNC_STATE_LOCK:
            state = _touch_state(path)
            state["pending"] = int(state["pending"]) + 1
            should_sync = int(state["pending"]) >= _FSYNC_BATCH_SIZE or (now - float(state["last_sync"])) >= _FSYNC_INTERVAL_SECONDS
            if should_sync:
                os.fsync(f.fileno())
                state["pending"] = 0
                state["last_sync"] = now
