"""Display-mode helpers for Source UI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
CATHEDRALCTL = REPO_ROOT / "tools" / "cathedralctl"
DEFERRED_QUEUE_STATE_PATH = REPO_ROOT / "workspace" / "state_runtime" / "vllm_deferred" / "queue_state.json"


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _queue_summary() -> dict[str, Any]:
    payload = _read_json(DEFERRED_QUEUE_STATE_PATH)
    entries = payload.get("entries") if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        entries = []
    rows = [item for item in entries if isinstance(item, dict)]
    deferred = [item for item in rows if str(item.get("status") or "") == "deferred"]
    review = [item for item in rows if str(item.get("status") or "") == "review_required"]
    completed = [item for item in rows if str(item.get("status") or "") == "completed"]
    return {
        "pending": len(deferred),
        "review_required": len(review),
        "completed": len(completed),
        "discord_pending": sum(1 for item in deferred if str(item.get("kind") or "") == "discord_message"),
        "router_pending": sum(1 for item in deferred if str(item.get("kind") or "") == "router_request"),
        "updated_at": payload.get("updated_at") if isinstance(payload, dict) else None,
    }


def _run_cathedralctl(target: str, action: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["bash", str(CATHEDRALCTL), target, action],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    output = (completed.stdout or "").strip()
    if completed.returncode != 0:
        return {
            "ok": False,
            "error": (completed.stderr or output or f"exit {completed.returncode}").strip()[:400],
        }
    try:
        payload = json.loads(output)
    except Exception:
        return {"ok": False, "error": f"invalid_status_payload:{output[:180]}"}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid_status_shape"}
    payload["ok"] = bool(payload.get("ok", True))
    return payload


def _enrich_status(payload: dict[str, Any]) -> dict[str, Any]:
    profile = str(payload.get("profile_current") or "unknown").strip() or "unknown"
    toggle_target = "work" if profile == "fishtank" else "fishtank"
    requested_mode = str(payload.get("requested_mode") or "auto").strip() or "auto"
    payload["mode_label"] = profile.upper()
    payload["toggle_target"] = toggle_target
    payload["toggle_label"] = f"Switch to {toggle_target.title()}"
    payload["queue"] = _queue_summary()
    payload["requested_mode"] = requested_mode
    return payload


def load_display_mode_status() -> dict[str, Any]:
    payload = _run_cathedralctl("fishtank", "status")
    if not payload.get("ok"):
        payload["queue"] = _queue_summary()
        return payload
    return _enrich_status(payload)


def toggle_display_mode() -> dict[str, Any]:
    current = load_display_mode_status()
    if not current.get("ok"):
        return current
    target = str(current.get("toggle_target") or "work")
    action = str(current.get("requested_mode") or "auto")
    if action not in {"on", "off", "auto"}:
        action = "auto"
    payload = _run_cathedralctl(target, action)
    if not payload.get("ok"):
        payload["queue"] = _queue_summary()
        return payload
    return _enrich_status(payload)
