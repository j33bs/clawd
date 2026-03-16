from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return json.loads(json.dumps(default))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(json.dumps(default))


def default_tasks_doc() -> dict[str, Any]:
    return {"schema_version": 1, "updated_at": utc_now_iso(), "tasks": []}


def default_projects_doc() -> dict[str, Any]:
    return {"schema_version": 1, "updated_at": utc_now_iso(), "projects": []}


def default_bridge_state_doc() -> dict[str, Any]:
    return {"schema_version": 1, "updated_at": utc_now_iso(), "deliveries": {}}


def ensure_state_files(tasks_path: Path, projects_path: Path, bridge_state_path: Path) -> None:
    for path, default in (
        (tasks_path, default_tasks_doc()),
        (projects_path, default_projects_doc()),
        (bridge_state_path, default_bridge_state_doc()),
    ):
        if not Path(path).is_file():
            write_atomic_json(path, default)


def load_tasks(path: Path) -> dict[str, Any]:
    return read_json(path, default_tasks_doc())


def save_tasks(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now_iso()
    write_atomic_json(path, payload)


def load_projects(path: Path) -> dict[str, Any]:
    return read_json(path, default_projects_doc())


def task_counts(tasks_doc: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in tasks_doc.get("tasks") or []:
        status = str(task.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def create_task(tasks_doc: dict[str, Any], *, title: str, project: str, details: str, created_by: str) -> dict[str, Any]:
    task_id = f"task-{utc_now_iso().replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
    task = {
        "id": task_id,
        "title": title.strip(),
        "project": project.strip(),
        "details": details.strip(),
        "status": "todo",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "created_by": created_by,
        "updated_by": created_by,
    }
    tasks = list(tasks_doc.get("tasks") or [])
    tasks.append(task)
    tasks_doc["tasks"] = tasks
    tasks_doc["updated_at"] = utc_now_iso()
    return task


def move_task(tasks_doc: dict[str, Any], *, task_id: str, status: str, moved_by: str) -> dict[str, Any]:
    normalized_status = str(status).strip().lower()
    for task in tasks_doc.get("tasks") or []:
        if str(task.get("id")) == task_id:
            task["status"] = normalized_status
            task["updated_at"] = utc_now_iso()
            task["updated_by"] = moved_by
            tasks_doc["updated_at"] = utc_now_iso()
            return task
    raise KeyError(task_id)

