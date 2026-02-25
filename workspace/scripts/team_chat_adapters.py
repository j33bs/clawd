#!/usr/bin/env python3
"""TeamChat planner/coder adapters with offline defaults and live router-backed mode."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from policy_router import PolicyRouter, build_chat_payload


ALLOWED_COMMAND_PATTERNS = [
    re.compile(r"^git\s+(status|diff|log)(\s|$)"),
    re.compile(r"^python3\s+-m\s+py_compile(\s|$)"),
    re.compile(r"^npm\s+test(\s|$)"),
    re.compile(r"^bash\s+workspace/scripts/verify_[A-Za-z0-9_.-]+\.sh(\s|$)"),
]

PAUSE_SENTINEL = "(pausing — no value to add)"


def _append_pause_log(decision: dict[str, Any], *, intent: str) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    log_path = repo_root / "workspace" / "state" / "pause_check_events.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "intent": intent,
        "enabled": bool(decision.get("enabled")),
        "decision": decision.get("decision"),
        "rationale": decision.get("rationale"),
        "signals": decision.get("signals", {}),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _pause_gate_text(intent: str, input_text: str, draft_text: str) -> tuple[str, dict[str, Any]]:
    env_on = str(os.getenv("OPENCLAW_PAUSE_CHECK", "0")).strip().lower() in {"1", "true", "yes", "on"}
    if not env_on:
        return draft_text, {
            "enabled": False,
            "decision": "proceed",
            "rationale": "pause check disabled",
            "signals": {"fills_space": 0.0, "value_add": 0.0, "silence_ok": 0.0},
            "felt_sense": None,
        }

    repo_root = Path(__file__).resolve().parents[2]
    memory_dir = repo_root / "workspace" / "memory"
    import sys

    if str(memory_dir) not in sys.path:
        sys.path.insert(0, str(memory_dir))
    from pause_check import pause_check  # type: ignore

    context = {
        "intent": intent,
        "source": "team_chat_adapters",
        "test_mode": str(os.getenv("OPENCLAW_PAUSE_CHECK_TEST_MODE", "0")).strip().lower()
        in {"1", "true", "yes", "on"},
    }
    decision = pause_check(input_text, draft_text, context=context, mode="router_pre_response")
    _append_pause_log(decision, intent=intent)
    if decision.get("decision") == "silence":
        return PAUSE_SENTINEL, decision
    return draft_text, decision


def _contains_shell_metacharacters(cmd: str) -> bool:
    return bool(re.search(r"[|;&`><]", cmd))


def _is_allowed_command(cmd: str, extra_patterns: list[str] | None = None) -> bool:
    cmd = cmd.strip()
    if not cmd or _contains_shell_metacharacters(cmd):
        return False
    patterns = list(ALLOWED_COMMAND_PATTERNS)
    if extra_patterns:
        for value in extra_patterns:
            patterns.append(re.compile(value))
    return any(p.match(cmd) for p in patterns)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _coerce_work_orders(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if not item.get("title"):
            continue
        out.append(
            {
                "id": str(item.get("id") or f"wo-{len(out)+1}"),
                "title": str(item.get("title") or ""),
                "goal": str(item.get("goal") or ""),
                "commands": [str(x) for x in item.get("commands", []) if isinstance(x, str)],
                "tests": [str(x) for x in item.get("tests", []) if isinstance(x, str)],
                "notes": str(item.get("notes") or ""),
            }
        )
    return out


@dataclass
class AdapterResult:
    ok: bool
    data: dict[str, Any]
    route: dict[str, Any]
    error: str | None = None


class PlannerAdapterBase:
    def plan(self, session_prompt: str, state: dict[str, Any]) -> AdapterResult:  # pragma: no cover - interface
        raise NotImplementedError

    def review(self, patch_report: dict[str, Any], state: dict[str, Any]) -> AdapterResult:  # pragma: no cover - interface
        raise NotImplementedError


class CoderAdapterBase:
    def execute(self, work_order: dict[str, Any], state: dict[str, Any]) -> AdapterResult:  # pragma: no cover - interface
        raise NotImplementedError


class FakePlannerAdapter(PlannerAdapterBase):
    def plan(self, session_prompt: str, state: dict[str, Any]) -> AdapterResult:
        work_orders = [
            {
                "id": "wo-1",
                "title": "Run deterministic checks",
                "goal": "Collect lightweight evidence without mutating routing logic",
                "commands": [
                    "git status --porcelain -uall",
                    "python3 -m py_compile workspace/scripts/policy_router.py",
                ],
                "tests": ["bash workspace/scripts/verify_policy_router.sh"],
                "notes": "Offline deterministic planning",
            }
        ]
        return AdapterResult(
            ok=True,
            data={
                "plan": {
                    "summary": "Perform one low-risk verification cycle",
                    "session_prompt": session_prompt,
                    "risk_level": "low",
                },
                "work_orders": work_orders,
            },
            route={
                "mode": "offline",
                "intent": "teamchat_planner",
                "provider": "fake_planner",
                "model": "fake/planner",
            },
        )

    def review(self, patch_report: dict[str, Any], state: dict[str, Any]) -> AdapterResult:
        status = patch_report.get("status", "unknown")
        decision = "accept" if status in {"ok", "noop"} else "revise"
        return AdapterResult(
            ok=True,
            data={
                "decision": decision,
                "reason": "offline review",
                "next_work_orders": [],
            },
            route={
                "mode": "offline",
                "intent": "teamchat_planner_review",
                "provider": "fake_planner",
                "model": "fake/planner",
            },
        )


class FakeCoderAdapter(CoderAdapterBase):
    def execute(self, work_order: dict[str, Any], state: dict[str, Any]) -> AdapterResult:
        tool_logs = []
        for command in work_order.get("commands", []):
            tool_logs.append(
                {
                    "command": command,
                    "allowed": True,
                    "exit_code": 0,
                    "stdout": "offline-ok",
                    "stderr": "",
                }
            )
        report = {
            "work_order_id": work_order.get("id"),
            "status": "ok",
            "files_changed": [],
            "commands_run": [t["command"] for t in tool_logs],
            "results": [{"command": t["command"], "exit_code": t["exit_code"]} for t in tool_logs],
            "notes": "offline coder simulation",
        }
        return AdapterResult(
            ok=True,
            data={"patch_report": report, "tool_calls": tool_logs},
            route={
                "mode": "offline",
                "intent": "teamchat_coder",
                "provider": "fake_coder",
                "model": "fake/coder",
            },
        )


class RouterLLMClient:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.router = PolicyRouter()

    def run_json(
        self,
        *,
        intent: str,
        input_text: str,
        trigger_phrase: str,
        prompt: str,
        max_tokens: int,
        validate_fn: Callable[[str], dict[str, Any] | None],
    ) -> AdapterResult:
        context = {"input_text": f"{trigger_phrase}\n{input_text}"}
        payload = build_chat_payload(prompt, temperature=0.0, max_tokens=max_tokens)
        result = self.router.execute_with_escalation(intent, payload, context_metadata=context, validate_fn=validate_fn)
        route_explain = self.router.explain_route(intent, context_metadata=context, payload=payload)
        route_meta = {
            "mode": "live",
            "intent": intent,
            "trigger_phrase": trigger_phrase,
            "selected_provider": result.get("provider"),
            "selected_model": result.get("model"),
            "reason_code": result.get("reason_code"),
            "route_explain": route_explain,
        }
        if not result.get("ok"):
            return AdapterResult(ok=False, data={}, route=route_meta, error=result.get("reason_code", "router_error"))

        response_text = str(result.get("text") or "")
        gated_text, pause_decision = _pause_gate_text(intent, input_text, response_text)
        route_meta["pause_check"] = pause_decision
        if pause_decision.get("enabled") and pause_decision.get("decision") == "silence":
            return AdapterResult(
                ok=False,
                data={},
                route=route_meta,
                error="paused_no_value_add",
            )

        parsed = result.get("parsed")
        if not isinstance(parsed, dict):
            parsed = validate_fn(gated_text)
        if not isinstance(parsed, dict):
            return AdapterResult(ok=False, data={}, route=route_meta, error="invalid_json_response")
        return AdapterResult(ok=True, data=parsed, route=route_meta)


class LivePlannerAdapter(PlannerAdapterBase):
    def __init__(self, client: RouterLLMClient):
        self.client = client

    def plan(self, session_prompt: str, state: dict[str, Any]) -> AdapterResult:
        prompt = (
            "You are planner agent. Return strict JSON with keys plan and work_orders. "
            "plan requires summary and risk_level. work_orders is array of small testable tasks with "
            "id,title,goal,commands[],tests[],notes. Use only allowlisted commands.\n"
            f"Task: {session_prompt}"
        )

        def _validate(text: str) -> dict[str, Any] | None:
            obj = _extract_json_object(text)
            if not obj:
                return None
            if not isinstance(obj.get("plan"), dict):
                return None
            orders = _coerce_work_orders(obj.get("work_orders"))
            if not orders:
                return None
            obj["work_orders"] = orders
            return obj

        return self.client.run_json(
            intent="coding",
            input_text=session_prompt,
            trigger_phrase="use chatgpt",
            prompt=prompt,
            max_tokens=900,
            validate_fn=_validate,
        )

    def review(self, patch_report: dict[str, Any], state: dict[str, Any]) -> AdapterResult:
        prompt = (
            "You are planner review agent. Return strict JSON with decision (accept|revise|request_input), "
            "reason, next_work_orders (array).\n"
            f"Patch report: {json.dumps(patch_report, ensure_ascii=True)}"
        )

        def _validate(text: str) -> dict[str, Any] | None:
            obj = _extract_json_object(text)
            if not obj:
                return None
            if obj.get("decision") not in {"accept", "revise", "request_input"}:
                return None
            obj["next_work_orders"] = _coerce_work_orders(obj.get("next_work_orders", []))
            return obj

        return self.client.run_json(
            intent="coding",
            input_text=patch_report.get("notes", "review patch report"),
            trigger_phrase="use chatgpt",
            prompt=prompt,
            max_tokens=500,
            validate_fn=_validate,
        )


class LiveCoderAdapter(CoderAdapterBase):
    def __init__(self, client: RouterLLMClient, *, max_commands_per_cycle: int, extra_allowlist: list[str] | None = None):
        self.client = client
        self.max_commands_per_cycle = max_commands_per_cycle
        self.extra_allowlist = extra_allowlist or []

    def _run_shell_command(self, command: str, repo_root: Path) -> dict[str, Any]:
        if not _is_allowed_command(command, self.extra_allowlist):
            return {
                "command": command,
                "allowed": False,
                "exit_code": 126,
                "stdout": "",
                "stderr": "command_not_allowlisted",
            }
        proc = subprocess.run(
            ["bash", "-lc", command],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "command": command,
            "allowed": True,
            "exit_code": int(proc.returncode),
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }

    def execute(self, work_order: dict[str, Any], state: dict[str, Any]) -> AdapterResult:
        prompt = (
            "You are coder agent. Return strict JSON with commands[] and notes. "
            "Commands must be from this allowlist: git status/diff/log, python3 -m py_compile, npm test, "
            "bash workspace/scripts/verify_*.sh. No pipes or shell operators.\n"
            f"Work order: {json.dumps(work_order, ensure_ascii=True)}"
        )

        def _validate(text: str) -> dict[str, Any] | None:
            obj = _extract_json_object(text)
            if not obj:
                return None
            commands = [str(x) for x in obj.get("commands", []) if isinstance(x, str)]
            if not commands:
                commands = [str(x) for x in work_order.get("commands", []) if isinstance(x, str)]
            obj["commands"] = commands
            return obj

        plan_result = self.client.run_json(
            intent="coding",
            input_text=work_order.get("goal", "execute work order"),
            trigger_phrase="use codex",
            prompt=prompt,
            max_tokens=700,
            validate_fn=_validate,
        )
        if not plan_result.ok:
            return plan_result

        commands = plan_result.data.get("commands", [])[: self.max_commands_per_cycle]
        tool_calls = []
        all_ok = True
        for command in commands:
            row = self._run_shell_command(command, self.client.repo_root)
            tool_calls.append(row)
            if row["exit_code"] != 0:
                all_ok = False

        diff_proc = subprocess.run(
            ["bash", "-lc", "git status --porcelain -uall"],
            cwd=str(self.client.repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        changed = []
        for line in diff_proc.stdout.splitlines():
            if len(line) >= 4:
                changed.append(line[3:])

        report = {
            "work_order_id": work_order.get("id"),
            "status": "ok" if all_ok else "failed",
            "files_changed": changed,
            "commands_run": [r["command"] for r in tool_calls],
            "results": [
                {"command": r["command"], "exit_code": r["exit_code"], "allowed": r["allowed"]} for r in tool_calls
            ],
            "notes": str(plan_result.data.get("notes") or ""),
        }
        return AdapterResult(ok=True, data={"patch_report": report, "tool_calls": tool_calls}, route=plan_result.route)


def build_adapters(
    *,
    live: bool,
    repo_root: Path,
    max_commands_per_cycle: int,
    extra_allowlist: list[str] | None = None,
) -> tuple[PlannerAdapterBase, CoderAdapterBase]:
    if not live:
        return FakePlannerAdapter(), FakeCoderAdapter()
    client = RouterLLMClient(repo_root=repo_root)
    return (
        LivePlannerAdapter(client),
        LiveCoderAdapter(client, max_commands_per_cycle=max_commands_per_cycle, extra_allowlist=extra_allowlist),
    )
