"""Shared relational-state helpers for Source UI and prompt harnesses."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
PAUSE_CHECK_LOG_PATH = REPO_ROOT / "workspace" / "state" / "pause_check_log.jsonl"
PHI_METRICS_PATH = REPO_ROOT / "workspace" / "governance" / "phi_metrics.md"
CONTRIBUTION_REGISTER_PATH = REPO_ROOT / "workspace" / "governance" / "CONTRIBUTION_REGISTER.md"
RELATIONSHIP_STATE_PATH = REPO_ROOT / "workspace" / "state_runtime" / "memory" / "relationship_state.json"
AROUSAL_STATE_PATH = REPO_ROOT / "workspace" / "state_runtime" / "memory" / "arousal_state.json"
TACTI_STATE_PATHS = (
    REPO_ROOT / "workspace" / "runtime" / "tacti_state.json",
    REPO_ROOT / "runtime" / "tacti_state.json",
)


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _read_pause_check(limit: int) -> list[dict[str, Any]]:
    if not PAUSE_CHECK_LOG_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = [line for line in PAUSE_CHECK_LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    except Exception as exc:
        return [{"error": str(exc)}]
    for line in lines[-max(1, int(limit)) :]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        signals = row.get("signals") if isinstance(row.get("signals"), dict) else {}
        rows.append(
            {
                "ts": row.get("ts", ""),
                "decision": row.get("decision", ""),
                "fills_space": signals.get("fills_space"),
                "value_add": signals.get("value_add"),
            }
        )
    return rows


def _read_diversity_index() -> float | None:
    if not PHI_METRICS_PATH.exists():
        return None
    try:
        for line in PHI_METRICS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "author_silhouette" not in line or "=" not in line:
                continue
            match = re.search(r"author_silhouette=(-?[\d.]+)", line)
            if match:
                return float(match.group(1))
    except Exception:
        return None
    return None


def _read_silence_per_being() -> list[dict[str, Any]]:
    if not CONTRIBUTION_REGISTER_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    pattern = re.compile(r"\|\s*([\w][\w ()\-_ext]*?)\s*\|\s*([A-Z]+)\s*\|[^|]+\|\s*(\d+)\s*behind")
    try:
        for line in CONTRIBUTION_REGISTER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = pattern.match(line)
            if not match:
                continue
            rows.append(
                {
                    "being": match.group(1).strip(),
                    "last_section": match.group(2).strip(),
                    "sections_behind": int(match.group(3)),
                }
            )
    except Exception as exc:
        return [{"error": str(exc)}]
    return rows


def _load_latest_session() -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    relationship_state = _read_json(RELATIONSHIP_STATE_PATH)
    arousal_state = _read_json(AROUSAL_STATE_PATH)

    if isinstance(relationship_state, dict):
        for session_id, payload in dict(relationship_state.get("sessions") or {}).items():
            if isinstance(payload, dict):
                merged[str(session_id)] = {"id": str(session_id), **payload}
    if isinstance(arousal_state, dict):
        for session_id, payload in dict(arousal_state.get("sessions") or {}).items():
            if not isinstance(payload, dict):
                continue
            merged.setdefault(str(session_id), {"id": str(session_id)}).update(payload)

    latest: dict[str, Any] = {}
    latest_ts: datetime | None = None
    for payload in merged.values():
        candidate_ts = _parse_iso(payload.get("updated_at"))
        if latest_ts is None or (candidate_ts is not None and candidate_ts > latest_ts):
            latest = payload
            latest_ts = candidate_ts
    return latest


def _load_tacti_state() -> dict[str, Any]:
    for path in TACTI_STATE_PATHS:
        payload = _read_json(path)
        if isinstance(payload, dict):
            return payload
    return {}


def _trust_note(session: dict[str, Any]) -> str:
    trust = session.get("trust_score")
    attunement = session.get("attunement_index")
    try:
        trust_value = float(trust)
    except Exception:
        trust_value = None
    try:
        attunement_value = float(attunement)
    except Exception:
        attunement_value = None

    if trust_value is not None and trust_value < 0.45:
        return "fragile"
    if attunement_value is not None and attunement_value < 0.40:
        return "misattuned"
    if trust_value is not None and trust_value < 0.65:
        return "watchful"
    if trust_value is not None:
        return "stable"
    return "unknown"


def derive_response_style(payload: dict[str, Any]) -> dict[str, Any]:
    pause_entries = list(payload.get("pause_check") or [])
    latest_pause = pause_entries[-1] if pause_entries else {}
    session = dict(payload.get("session") or {})
    tacti = dict(payload.get("tacti") or {})

    fills_space = latest_pause.get("fills_space")
    value_add = latest_pause.get("value_add")
    session_arousal = session.get("arousal")
    tacti_arousal = tacti.get("arousal")
    attunement = session.get("attunement_index")
    trust = session.get("trust_score")
    unresolved_threads = session.get("unresolved_threads")
    di_alert = bool(payload.get("di_alert"))

    def _float(value: Any) -> float | None:
        try:
            return float(value)
        except Exception:
            return None

    fills_value = _float(fills_space)
    value_add_value = _float(value_add)
    session_arousal_value = _float(session_arousal)
    tacti_arousal_value = _float(tacti_arousal)
    attunement_value = _float(attunement)
    trust_value = _float(trust)

    arousal_values = [value for value in [session_arousal_value, tacti_arousal_value] if value is not None]
    mode = "steady"
    reason = "Relational signals are stable enough for a direct, proportionate reply."
    directives = [
        "Keep the reply concise and specific.",
        "Match the user's actual ask instead of broadening scope.",
    ]

    if fills_value is not None and value_add_value is not None and fills_value >= 0.65 and value_add_value <= 0.45:
        mode = "listen_first"
        reason = "Recent pause-check signals show filler risk outpacing value."
        directives = [
            "Do not fill silence or answer beyond the ask.",
            "Lead with the minimum useful response and stop when the point is made.",
        ]
    elif arousal_values and max(arousal_values) >= 0.78:
        mode = "de_escalate"
        reason = "Arousal is elevated, so the reply should lower pressure rather than add intensity."
        directives = [
            "Use short sentences and calm language.",
            "Offer one concrete next step instead of a menu of options.",
        ]
    elif (attunement_value is not None and attunement_value < 0.40) or (trust_value is not None and trust_value < 0.45):
        mode = "repair"
        reason = "Attunement or trust is weak enough that careful acknowledgment matters more than momentum."
        directives = [
            "Avoid over-claiming understanding or certainty.",
            "Acknowledge friction plainly before steering the conversation.",
        ]
    elif int(unresolved_threads or 0) > 0:
        mode = "close_loops"
        reason = "There are unresolved threads, so closing commitments should beat branching into new work."
        directives = [
            "Resolve or explicitly park open loops before opening new ones.",
            "Name the status of outstanding work rather than assuming closure.",
        ]

    if di_alert:
        directives.append("If multiple beings are replying, add a distinct angle instead of echoing the same framing.")

    return {
        "mode": mode,
        "reason": reason,
        "directives": directives,
        "signals": {
            "fills_space": fills_value,
            "value_add": value_add_value,
            "session_arousal": session_arousal_value,
            "tacti_arousal": tacti_arousal_value,
            "attunement_index": attunement_value,
            "trust_score": trust_value,
            "unresolved_threads": int(unresolved_threads or 0),
            "di_alert": di_alert,
        },
    }


def load_relational_state(limit: int = 3) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "pause_check": _read_pause_check(limit=limit),
        "diversity_index": _read_diversity_index(),
        "silence_per_being": _read_silence_per_being(),
        "session": _load_latest_session(),
        "tacti": _load_tacti_state(),
    }
    payload["di_alert"] = payload["diversity_index"] is not None and float(payload["diversity_index"]) < 0.0
    payload["trust_note"] = _trust_note(dict(payload.get("session") or {}))
    payload["response_style"] = derive_response_style(payload)
    payload["signal_count"] = int(bool(payload["pause_check"])) + int(bool(payload["diversity_index"] is not None)) + int(
        bool(payload["session"])
    ) + int(bool(payload["tacti"]))
    return payload


def build_relational_prompt_lines(
    *,
    harness: dict[str, Any] | None = None,
    limit: int = 4,
) -> list[str]:
    payload = load_relational_state(limit=3)
    if int(payload.get("signal_count") or 0) <= 0:
        return []

    response_style = dict(payload.get("response_style") or {})
    mode = str(response_style.get("mode") or "steady").strip() or "steady"
    reason = str(response_style.get("reason") or "").strip()
    directives = [str(line).strip() for line in list(response_style.get("directives") or []) if str(line).strip()]

    harness_modes = {}
    if isinstance(harness, dict):
        harness_modes = dict(harness.get("relational_modes") or {})
    directives.extend(str(line).strip() for line in list(harness_modes.get(mode) or []) if str(line).strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for line in directives:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)

    lines = [f"- Mode: {mode}."]
    if reason:
        lines.append(f"- Reason: {reason}")
    for directive in deduped:
        lines.append(f"- {directive}")
    return lines[: max(1, int(limit))]


__all__ = [
    "build_relational_prompt_lines",
    "derive_response_style",
    "load_relational_state",
]
