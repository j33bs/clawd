#!/usr/bin/env python3
"""Ensure local OpenClaw cron jobs match in-repo templates."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_FILE = REPO_ROOT / "workspace" / "automation" / "cron_jobs.json"


def load_templates(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    if not isinstance(jobs, list):
        raise ValueError("Template file must contain a top-level jobs array")
    out: list[dict[str, Any]] = []
    for idx, job in enumerate(jobs):
        if not isinstance(job, dict):
            raise ValueError(f"Job entry {idx} must be an object")
        name = str(job.get("name", "")).strip()
        session_target = str(job.get("sessionTarget", "")).strip()
        wake_mode = str(job.get("wakeMode", "now")).strip() or "now"
        schedule = job.get("schedule")
        command = str(job.get("command", "")).strip()
        if not name:
            raise ValueError(f"Job entry {idx} missing name")
        if session_target not in {"main", "isolated"}:
            raise ValueError(f"Job {name}: sessionTarget must be main|isolated")
        if wake_mode not in {"now", "next-heartbeat"}:
            raise ValueError(f"Job {name}: wakeMode must be now|next-heartbeat")
        if not isinstance(schedule, dict):
            raise ValueError(f"Job {name}: schedule must be an object")
        expr = str(schedule.get("expr", "")).strip()
        tz = str(schedule.get("tz", "")).strip()
        if not expr:
            raise ValueError(f"Job {name}: schedule.expr required")
        if not tz:
            raise ValueError(f"Job {name}: schedule.tz required")
        if not command:
            raise ValueError(f"Job {name}: command required")
        out.append(
            {
                "name": name,
                "sessionTarget": session_target,
                "wakeMode": wake_mode,
                "schedule": {"expr": expr, "tz": tz},
                "command": command,
            }
        )
    return out


def payload_kind(template: dict[str, Any]) -> str:
    return "systemEvent" if template["sessionTarget"] == "main" else "agentTurn"


def heartbeat_required(template: dict[str, Any]) -> bool:
    return template["sessionTarget"] == "main" and template.get("wakeMode", "now") == "now"


def template_requires_heartbeat(templates: list[dict[str, Any]]) -> bool:
    return any(heartbeat_required(template) for template in templates)


def normalize_existing(job: dict[str, Any]) -> dict[str, Any]:
    payload = job.get("payload", {}) if isinstance(job.get("payload"), dict) else {}
    schedule = job.get("schedule", {}) if isinstance(job.get("schedule"), dict) else {}
    return {
        "id": str(job.get("id", "")),
        "name": str(job.get("name", "")).strip(),
        "enabled": bool(job.get("enabled", False)),
        "sessionTarget": str(job.get("sessionTarget", "")).strip(),
        "wakeMode": str(job.get("wakeMode", "")).strip(),
        "schedule": {
            "expr": str(schedule.get("expr", "")).strip(),
            "tz": str(schedule.get("tz", "")).strip(),
        },
        "payload": {
            "kind": str(payload.get("kind", "")).strip(),
            "text": str(payload.get("text", "")).strip(),
            "message": str(payload.get("message", "")).strip(),
        },
    }


def render_command_for_template(template: dict[str, Any]) -> str:
    return template["command"].strip()


def job_matches_template(existing: dict[str, Any], template: dict[str, Any]) -> bool:
    payload = existing["payload"]
    expected_kind = payload_kind(template)
    expected_command = render_command_for_template(template)
    actual_command = payload["text"] if expected_kind == "systemEvent" else payload["message"]
    return (
        existing["name"] == template["name"]
        and existing["sessionTarget"] == template["sessionTarget"]
        and existing["wakeMode"] == template["wakeMode"]
        and existing["schedule"]["expr"] == template["schedule"]["expr"]
        and existing["schedule"]["tz"] == template["schedule"]["tz"]
        and payload["kind"] == expected_kind
        and actual_command == expected_command
        and existing["enabled"]
    )


def _openclaw_output_to_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    for idx, ch in enumerate(text):
        if ch in "{[":
            candidate = text[idx:]
            return json.loads(candidate)
    raise ValueError("No JSON payload in openclaw output")


def run_openclaw(args: list[str], openclaw_bin: str = "openclaw") -> dict[str, Any]:
    proc = subprocess.run(
        [openclaw_bin, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"openclaw {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return _openclaw_output_to_json(proc.stdout)


def list_jobs(
    openclaw_bin: str,
    runner: Callable[[list[str], str], dict[str, Any]] = run_openclaw,
) -> list[dict[str, Any]]:
    payload = runner(["cron", "list", "--all", "--json"], openclaw_bin)
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return []
    out = [normalize_existing(job) for job in jobs if isinstance(job, dict)]
    out.sort(key=lambda item: item["name"])
    return out


def find_job_by_name(jobs: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    matches = [job for job in jobs if job["name"] == name]
    if not matches:
        return None
    matches.sort(key=lambda item: item["id"])
    return matches[0]


def build_add_args(template: dict[str, Any]) -> list[str]:
    args = [
        "cron",
        "add",
        "--name",
        template["name"],
        "--cron",
        template["schedule"]["expr"],
        "--tz",
        template["schedule"]["tz"],
        "--session",
        template["sessionTarget"],
        "--wake",
        template["wakeMode"],
    ]
    if payload_kind(template) == "systemEvent":
        args.extend(["--system-event", template["command"]])
    else:
        args.extend(["--message", template["command"], "--no-deliver"])
    return args


def build_edit_args(job_id: str, template: dict[str, Any]) -> list[str]:
    args = [
        "cron",
        "edit",
        job_id,
        "--name",
        template["name"],
        "--cron",
        template["schedule"]["expr"],
        "--tz",
        template["schedule"]["tz"],
        "--session",
        template["sessionTarget"],
        "--wake",
        template["wakeMode"],
        "--enable",
    ]
    if payload_kind(template) == "systemEvent":
        args.extend(["--system-event", template["command"]])
    else:
        args.extend(["--message", template["command"], "--no-deliver"])
    return args


def ensure_jobs(
    templates: list[dict[str, Any]],
    *,
    openclaw_bin: str = "openclaw",
    apply: bool = True,
    runner: Callable[[list[str], str], dict[str, Any]] = run_openclaw,
) -> dict[str, Any]:
    jobs = list_jobs(openclaw_bin, runner=runner)
    actions: list[dict[str, Any]] = []
    for template in templates:
        existing = find_job_by_name(jobs, template["name"])
        if existing is None:
            action = {"name": template["name"], "operation": "create"}
            if apply:
                runner(build_add_args(template), openclaw_bin)
                jobs = list_jobs(openclaw_bin, runner=runner)
                existing = find_job_by_name(jobs, template["name"])
                action["job_id"] = existing["id"] if existing else None
            actions.append(action)
            continue
        if job_matches_template(existing, template):
            actions.append({"name": template["name"], "operation": "unchanged", "job_id": existing["id"]})
            continue
        action = {"name": template["name"], "operation": "update", "job_id": existing["id"]}
        if apply:
            runner(build_edit_args(existing["id"], template), openclaw_bin)
            jobs = list_jobs(openclaw_bin, runner=runner)
        actions.append(action)
    return {
        "applied": apply,
        "heartbeat_required": template_requires_heartbeat(templates),
        "actions": actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure local OpenClaw cron jobs from template")
    parser.add_argument("--template-file", default=str(DEFAULT_TEMPLATE_FILE))
    parser.add_argument("--openclaw-bin", default="openclaw")
    parser.add_argument("--check", action="store_true", help="Plan only (no changes)")
    args = parser.parse_args()

    templates = load_templates(Path(args.template_file).expanduser())
    summary = ensure_jobs(
        templates,
        openclaw_bin=args.openclaw_bin,
        apply=not args.check,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
