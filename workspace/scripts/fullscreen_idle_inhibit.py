#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from typing import Iterable

POLL_SECONDS = max(1.0, float(os.environ.get("OPENCLAW_FULLSCREEN_INHIBIT_POLL_SECONDS", "5")))
APP_ID = os.environ.get("OPENCLAW_FULLSCREEN_INHIBIT_APP_ID", "openclaw-fullscreen-inhibit")
REASON = os.environ.get("OPENCLAW_FULLSCREEN_INHIBIT_REASON", "Fullscreen application active")
FULLSCREEN_ATOM = "_NET_WM_STATE_FULLSCREEN"
WINDOW_ID_PATTERN = re.compile(r"0x[0-9a-fA-F]+")
RUNNING = True


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def parse_window_ids(raw: str) -> list[str]:
    return WINDOW_ID_PATTERN.findall(str(raw or ""))


def parse_atoms(raw: str) -> set[str]:
    return {token.strip().rstrip(",") for token in re.findall(r"_NET_WM_STATE_[A-Z_]+", str(raw or ""))}


def is_fullscreen_state(raw: str) -> bool:
    return FULLSCREEN_ATOM in parse_atoms(raw)


def list_stacked_windows() -> list[str]:
    result = _run("xprop", "-root", "_NET_CLIENT_LIST_STACKING")
    if result.returncode != 0:
        return []
    return parse_window_ids(result.stdout)


def window_is_fullscreen(window_id: str) -> bool:
    if not window_id:
        return False
    result = _run("xprop", "-id", window_id, "_NET_WM_STATE")
    if result.returncode != 0:
        return False
    return is_fullscreen_state(result.stdout)


def window_label(window_id: str) -> str:
    if not window_id:
        return ""
    name = _run("xprop", "-id", window_id, "_NET_WM_NAME")
    if name.returncode == 0 and "=" in name.stdout:
        return name.stdout.split("=", 1)[1].strip().strip('"')
    klass = _run("xprop", "-id", window_id, "WM_CLASS")
    if klass.returncode == 0 and "=" in klass.stdout:
        return klass.stdout.split("=", 1)[1].strip()
    return window_id


def detect_fullscreen_window(window_ids: Iterable[str] | None = None) -> str:
    candidates = list(window_ids) if window_ids is not None else list_stacked_windows()
    for window_id in reversed(candidates):
        if window_is_fullscreen(window_id):
            return window_id
    return ""


def start_inhibitor() -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            "gnome-session-inhibit",
            "--inhibit",
            "idle",
            "--app-id",
            APP_ID,
            "--reason",
            REASON,
            "--inhibit-only",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_inhibitor(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _handle_signal(signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False
    print(f"signal={signum} stop_requested=1", flush=True)


def main() -> int:
    if os.environ.get("XDG_SESSION_TYPE", "").lower() != "x11":
        print("status=disabled reason=non_x11_session", flush=True)
        return 0

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    inhibitor: subprocess.Popen[bytes] | None = None
    active_window = ""
    try:
        while RUNNING:
            fullscreen_window = detect_fullscreen_window()
            if fullscreen_window and (inhibitor is None or inhibitor.poll() is not None):
                inhibitor = start_inhibitor()
                active_window = fullscreen_window
                print(
                    f"status=inhibiting window={fullscreen_window} label={window_label(fullscreen_window)}",
                    flush=True,
                )
            elif not fullscreen_window and inhibitor is not None:
                stop_inhibitor(inhibitor)
                inhibitor = None
                if active_window:
                    print(f"status=released window={active_window}", flush=True)
                    active_window = ""
            elif fullscreen_window:
                active_window = fullscreen_window
            time.sleep(POLL_SECONDS)
    finally:
        stop_inhibitor(inhibitor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
