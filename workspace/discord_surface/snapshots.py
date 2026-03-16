from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import load_projects, load_tasks, task_counts, utc_now_iso


SIM_STALE_AFTER_SECONDS = 24 * 60 * 60
CONSENSUS_STALE_AFTER_SECONDS = 30 * 60


def _file_stamp(path: Path) -> str | None:
    path = Path(path)
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _load_json_payload(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _sim_stale_after_seconds(payload: dict[str, Any] | None) -> int:
    if isinstance(payload, dict) and isinstance(payload.get("symbols"), dict):
        return CONSENSUS_STALE_AFTER_SECONDS
    return SIM_STALE_AFTER_SECONDS


def _sim_generated_at(path: Path) -> str | None:
    path = Path(path)
    if not path.is_file():
        return None
    payload = _load_json_payload(path)
    if payload is None:
        return _file_stamp(path)
    return payload.get("generated_at") or _file_stamp(path)


def _is_stale_generated_at(text: str | None, *, stale_after_seconds: int) -> bool:
    generated_at = _parse_utc_iso(text)
    if generated_at is None:
        return False
    age_seconds = (datetime.now(timezone.utc) - generated_at).total_seconds()
    return age_seconds > stale_after_seconds


def _service_status(service_name: str) -> str:
    if platform.system() == "Darwin":
        uid = os.getuid()
        try:
            result = subprocess.run(
                ["launchctl", "print", f"gui/{uid}/{service_name}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return "unknown"
        if result.returncode != 0:
            return "not_loaded"
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("state = "):
                return line.split("=", 1)[1].strip()
            if line.startswith("job state = "):
                return line.split("=", 1)[1].strip()
        return "loaded"
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service_name],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return "unknown"
    text = (result.stdout or result.stderr or "").strip()
    return text or "unknown"


def build_ops_snapshot(*, tasks_path: Path, projects_path: Path, sim_path: Path, health_services: list[str], log_paths: list[Path]) -> dict[str, Any]:
    sim_payload = _load_json_payload(sim_path)
    sim_generated_at = _sim_generated_at(sim_path)
    sim_display = sim_generated_at
    if _is_stale_generated_at(sim_generated_at, stale_after_seconds=_sim_stale_after_seconds(sim_payload)):
        sim_display = f"{sim_generated_at} stale"
    services = {name: _service_status(name) for name in health_services}
    files = {
        "tasks_json": _file_stamp(tasks_path),
        "projects_json": _file_stamp(projects_path),
        "sim_json": sim_display,
    }
    for index, log_path in enumerate(log_paths[:5], start=1):
        files[f"log_{index}"] = _file_stamp(log_path)
    return {
        "generated_at": utc_now_iso(),
        "services": services,
        "files": files,
    }


def build_sim_snapshot(sim_path: Path) -> dict[str, Any]:
    path = Path(sim_path)
    if not path.is_file():
        return {"status": "missing", "generated_at": utc_now_iso(), "sim_path": str(path)}
    payload = json.loads(path.read_text(encoding="utf-8"))
    generated_at = payload.get("generated_at") or utc_now_iso()
    status = "stale" if _is_stale_generated_at(generated_at, stale_after_seconds=_sim_stale_after_seconds(payload)) else "ok"
    if isinstance(payload.get("symbols"), dict):
        rows = []
        for symbol, value in payload.get("symbols", {}).items():
            if not isinstance(value, dict):
                continue
            decision = value.get("decision") or {}
            sentiment = (value.get("agents") or {}).get("sentiment") or {}
            rows.append(
                {
                    "symbol": symbol,
                    "action": decision.get("action"),
                    "bias": decision.get("bias"),
                    "confidence": decision.get("confidence"),
                    "risk_state": decision.get("risk_state"),
                    "sentiment": sentiment.get("score"),
                    "model_resolved": decision.get("model_resolved"),
                }
            )
        inputs = ((payload.get("external_signal") or {}).get("inputs") or {})
        return {
            "status": status,
            "kind": "consensus",
            "generated_at": generated_at,
            "rows": rows[:4],
            "external_inputs": {
                name: (value or {}).get("status")
                for name, value in inputs.items()
                if isinstance(value, dict)
            },
        }
    sims: dict[str, Any] = {}
    for name, value in payload.items():
        if not str(name).startswith("SIM_") or not isinstance(value, dict):
            continue
        sims[name] = {
            "equity": value.get("equity"),
            "pnl_pct": value.get("pnl_pct"),
            "dd_pct": value.get("dd_pct"),
            "trades_total": value.get("trades_total"),
        }
    return {
        "status": status,
        "kind": "legacy_sim",
        "generated_at": generated_at,
        "command": payload.get("command"),
        "sims": sims,
    }


def build_project_snapshot(tasks_path: Path, projects_path: Path) -> dict[str, Any]:
    tasks_doc = load_tasks(tasks_path)
    projects_doc = load_projects(projects_path)
    projects = list(projects_doc.get("projects") or [])
    return {
        "generated_at": utc_now_iso(),
        "task_counts": task_counts(tasks_doc),
        "project_count": len(projects),
        "projects": projects[:10],
    }


def format_ops_message(snapshot: dict[str, Any]) -> str:
    parts = [f"ops-health {snapshot.get('generated_at')}"]
    services = snapshot.get("services") or {}
    if services:
        parts.append("services " + ", ".join(f"{name}={status}" for name, status in services.items()))
    files = snapshot.get("files") or {}
    file_bits = [f"{name}:{stamp or 'missing'}" for name, stamp in files.items() if stamp]
    if file_bits:
        parts.append("files " + ", ".join(file_bits[:4]))
    return "\n".join(parts)


def format_sim_message(snapshot: dict[str, Any]) -> str:
    if snapshot.get("status") == "missing":
        return f"sim-status unavailable path={snapshot.get('sim_path')}"
    if snapshot.get("status") == "stale":
        if snapshot.get("kind") == "consensus":
            return f"sim-status stale generated_at={snapshot.get('generated_at')} source=dali-feedback"
        return f"sim-status stale generated_at={snapshot.get('generated_at')}"
    if snapshot.get("kind") == "consensus":
        parts = [f"sim-status {snapshot.get('generated_at')} source=dali-feedback"]
        inputs = snapshot.get("external_inputs") or {}
        if inputs:
            parts.append("inputs " + ", ".join(f"{name}={status}" for name, status in inputs.items()))
        for row in snapshot.get("rows") or []:
            parts.append(
                f"{row.get('symbol')} action={row.get('action')} bias={row.get('bias')} conf={row.get('confidence')} risk={row.get('risk_state')} sentiment={row.get('sentiment')}"
            )
        return "\n".join(parts[:5])
    parts = [f"sim-status {snapshot.get('generated_at')}"]
    for name, row in (snapshot.get("sims") or {}).items():
        parts.append(
            f"{name} equity={row.get('equity')} pnl={row.get('pnl_pct')} dd={row.get('dd_pct')} trades={row.get('trades_total')}"
        )
    return "\n".join(parts[:4])


def format_project_message(snapshot: dict[str, Any]) -> str:
    counts = snapshot.get("task_counts") or {}
    projects = snapshot.get("projects") or []
    parts = [f"project-status projects={snapshot.get('project_count', 0)} tasks={counts}"]
    if projects:
        parts.extend(
            f"{project.get('id') or project.get('name')}: {project.get('status', 'unknown')} {project.get('summary', '')}".strip()
            for project in projects[:3]
        )
    return "\n".join(parts)
