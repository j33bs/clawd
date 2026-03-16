from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_json, load_json, utc_now_iso
from .logging_utils import JsonlLogger
from .paths import AESTHETIC_EVENTS_DIR, RUNTIME_LOGS, ensure_runtime_dirs


class AestheticFeedbackStore:
    def __init__(self, *, root: Path = AESTHETIC_EVENTS_DIR):
        ensure_runtime_dirs()
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self.log = JsonlLogger(RUNTIME_LOGS / "aesthetic_feedback.log")

    def _load_index(self) -> dict[str, Any]:
        payload = load_json(self.index_path, {"events": [], "likes": {}, "last_event_id": None})
        if not isinstance(payload, dict):
            return {"events": [], "likes": {}, "last_event_id": None}
        payload.setdefault("events", [])
        payload.setdefault("likes", {})
        payload.setdefault("last_event_id", None)
        return payload

    def _save_index(self, payload: dict[str, Any]) -> None:
        atomic_write_json(self.index_path, payload)

    def capture(
        self,
        *,
        command: str,
        renderer_state: dict[str, Any],
        telemetry_snapshot: dict[str, Any],
        camera: dict[str, Any],
    ) -> str:
        ts = utc_now_iso()
        event_id = hashlib.sha256(f"{ts}|{command}".encode("utf-8")).hexdigest()[:16]
        payload = {
            "event_id": event_id,
            "ts": ts,
            "command": str(command),
            "particle_state": renderer_state.get("particle_state", {}),
            "shader_parameters": renderer_state.get("shader_parameters", {}),
            "telemetry_snapshot": telemetry_snapshot,
            "camera_position": camera,
        }
        atomic_write_json(self.root / f"{event_id}.json", payload)

        index = self._load_index()
        events = index.get("events")
        if isinstance(events, list):
            events.append({"event_id": event_id, "ts": ts, "command": str(command)})
            index["events"] = events[-300:]
        index["last_event_id"] = event_id
        self._save_index(index)
        self.log.log("aesthetic_capture", event_id=event_id, command=str(command))
        return event_id

    def prefer(self, event_id: str, delta: float = 1.0) -> dict[str, Any]:
        index = self._load_index()
        likes = index.get("likes")
        if not isinstance(likes, dict):
            likes = {}
            index["likes"] = likes
        likes[event_id] = float(likes.get(event_id, 0.0)) + float(delta)
        self._save_index(index)
        self.log.log("aesthetic_prefer", event_id=event_id, score=likes[event_id])
        return {"event_id": event_id, "score": likes[event_id]}

    def latest_event_id(self) -> str | None:
        index = self._load_index()
        value = index.get("last_event_id")
        if isinstance(value, str) and value.strip():
            return value
        return None

    def bias_vector(self) -> dict[str, float]:
        index = self._load_index()
        likes = index.get("likes") if isinstance(index, dict) else None
        if not isinstance(likes, dict) or not likes:
            return {
                "luminosity_bias": 0.0,
                "turbulence_bias": 0.0,
                "velocity_bias": 0.0,
            }

        total_weight = 0.0
        luminosity = 0.0
        turbulence = 0.0
        velocity = 0.0
        for event_id, weight_raw in likes.items():
            weight = max(0.0, float(weight_raw))
            if weight <= 0.0:
                continue
            event_path = self.root / f"{event_id}.json"
            event = load_json(event_path, {})
            shader = event.get("shader_parameters") if isinstance(event, dict) else None
            if not isinstance(shader, dict):
                continue
            total_weight += weight
            luminosity += weight * float(shader.get("luminosity", 0.0))
            turbulence += weight * float(shader.get("turbulence", 0.0))
            velocity += weight * float(shader.get("velocity", 0.0))

        if total_weight <= 0:
            return {
                "luminosity_bias": 0.0,
                "turbulence_bias": 0.0,
                "velocity_bias": 0.0,
            }
        return {
            "luminosity_bias": luminosity / total_weight,
            "turbulence_bias": turbulence / total_weight,
            "velocity_bias": velocity / total_weight,
        }
