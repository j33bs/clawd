from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

try:  # pragma: no cover - optional dependency
    import jsonschema  # type: ignore
except Exception:  # pragma: no cover
    jsonschema = None


class ValidationError(ValueError):
    pass


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((_SCHEMA_DIR / name).read_text(encoding="utf-8"))


def validator_mode() -> str:
    return "jsonschema" if jsonschema is not None else "lite"


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _require_keys(obj: dict[str, Any], required: set[str], allowed: set[str], where: str) -> None:
    _ensure(required.issubset(obj.keys()), f"{where} missing required fields")
    _ensure(set(obj.keys()).issubset(allowed), f"{where} has additional properties")


def _validate_job_lite(job: dict[str, Any]) -> None:
    required = {"job_id", "job_type", "created_at_utc", "payload", "budgets", "tool_policy"}
    _require_keys(job, required=required, allowed=required | {"meta"}, where="job")

    job_id = job["job_id"]
    _ensure(isinstance(job_id, str) and job_id.startswith("job-"), "invalid job_id")
    _ensure(job_id.replace("-", "").isalnum() and job_id == job_id.lower(), "job_id must be lowercase alnum with dashes")
    _ensure(12 <= len(job_id) <= 40, "invalid job_id length")

    job_type = job["job_type"]
    _ensure(job_type in {"repo_index_task", "test_runner_task", "doc_compactor_task"}, "invalid job_type")

    created = job["created_at_utc"]
    _ensure(isinstance(created, str) and "T" in created and created.endswith("Z"), "created_at_utc must be UTC ISO-like")

    payload = job["payload"]
    _ensure(isinstance(payload, dict), "payload must be object")

    budgets = job["budgets"]
    _ensure(isinstance(budgets, dict), "budgets must be object")
    budget_keys = {"max_wall_time_sec", "max_tool_calls", "max_output_bytes", "max_concurrency_slots"}
    _require_keys(budgets, required=budget_keys, allowed=budget_keys, where="budgets")
    for key in budget_keys:
        _ensure(isinstance(budgets[key], int), f"budgets.{key} must be int")
    _ensure(1 <= budgets["max_wall_time_sec"] <= 7200, "budgets.max_wall_time_sec out of range")
    _ensure(0 <= budgets["max_tool_calls"] <= 500, "budgets.max_tool_calls out of range")
    _ensure(1024 <= budgets["max_output_bytes"] <= 104857600, "budgets.max_output_bytes out of range")
    _ensure(1 <= budgets["max_concurrency_slots"] <= 8, "budgets.max_concurrency_slots out of range")

    tool_policy = job["tool_policy"]
    _ensure(isinstance(tool_policy, dict), "tool_policy must be object")
    tp_keys = {"allow_network", "allow_subprocess", "allowed_tools"}
    _require_keys(tool_policy, required=tp_keys, allowed=tp_keys, where="tool_policy")
    _ensure(isinstance(tool_policy["allow_network"], bool), "tool_policy.allow_network must be bool")
    _ensure(isinstance(tool_policy["allow_subprocess"], bool), "tool_policy.allow_subprocess must be bool")
    allowed_tools = tool_policy["allowed_tools"]
    _ensure(isinstance(allowed_tools, list), "tool_policy.allowed_tools must be list")
    _ensure(len(allowed_tools) <= 32, "tool_policy.allowed_tools too long")
    _ensure(all(isinstance(item, str) and 1 <= len(item) <= 64 for item in allowed_tools), "tool_policy.allowed_tools invalid entry")


def _validate_schema_lite(schema_name: str, payload: dict[str, Any]) -> None:
    _ensure(isinstance(payload, dict), f"{schema_name} payload must be object")

    if schema_name == "repo_index_task.schema.json":
        required = {"include_globs", "max_files", "max_file_bytes"}
        allowed = required | {"exclude_globs", "keywords"}
        _require_keys(payload, required=required, allowed=allowed, where="repo_index_task")
        _ensure(isinstance(payload["include_globs"], list) and 1 <= len(payload["include_globs"]) <= 16, "include_globs invalid")
        _ensure(all(isinstance(x, str) and len(x) <= 128 for x in payload["include_globs"]), "include_globs entries invalid")
        _ensure(isinstance(payload["max_files"], int) and 1 <= payload["max_files"] <= 50000, "max_files invalid")
        _ensure(
            isinstance(payload["max_file_bytes"], int) and 128 <= payload["max_file_bytes"] <= 1048576,
            "max_file_bytes invalid",
        )
        if "exclude_globs" in payload:
            _ensure(isinstance(payload["exclude_globs"], list) and len(payload["exclude_globs"]) <= 16, "exclude_globs invalid")
            _ensure(all(isinstance(x, str) and len(x) <= 128 for x in payload["exclude_globs"]), "exclude_globs entries invalid")
        if "keywords" in payload:
            _ensure(isinstance(payload["keywords"], list) and len(payload["keywords"]) <= 32, "keywords invalid")
            _ensure(all(isinstance(x, str) and len(x) <= 64 for x in payload["keywords"]), "keywords entries invalid")

    elif schema_name == "test_runner_task.schema.json":
        required = {"commands", "timeout_sec"}
        allowed = required | {"cwd", "env_allow"}
        _require_keys(payload, required=required, allowed=allowed, where="test_runner_task")
        commands = payload["commands"]
        _ensure(isinstance(commands, list) and 1 <= len(commands) <= 32, "commands invalid")
        for argv in commands:
            _ensure(isinstance(argv, list) and 1 <= len(argv) <= 64, "command argv invalid")
            _ensure(all(isinstance(part, str) and 1 <= len(part) <= 256 for part in argv), "command part invalid")
        _ensure(isinstance(payload["timeout_sec"], int) and 1 <= payload["timeout_sec"] <= 3600, "timeout_sec invalid")
        if "cwd" in payload:
            _ensure(isinstance(payload["cwd"], str) and len(payload["cwd"]) <= 512, "cwd invalid")
        if "env_allow" in payload:
            _ensure(isinstance(payload["env_allow"], list) and len(payload["env_allow"]) <= 64, "env_allow invalid")
            _ensure(all(isinstance(key, str) and 1 <= len(key) <= 128 for key in payload["env_allow"]), "env_allow entries invalid")

    elif schema_name == "doc_compactor_task.schema.json":
        required = {"inputs", "max_input_bytes", "max_output_bytes"}
        allowed = required | {"title"}
        _require_keys(payload, required=required, allowed=allowed, where="doc_compactor_task")
        inputs = payload["inputs"]
        _ensure(isinstance(inputs, list) and 1 <= len(inputs) <= 64, "inputs invalid")
        _ensure(all(isinstance(path, str) and 1 <= len(path) <= 512 for path in inputs), "inputs entries invalid")
        _ensure(
            isinstance(payload["max_input_bytes"], int) and 128 <= payload["max_input_bytes"] <= 10485760,
            "max_input_bytes invalid",
        )
        _ensure(
            isinstance(payload["max_output_bytes"], int) and 128 <= payload["max_output_bytes"] <= 1048576,
            "max_output_bytes invalid",
        )
        if "title" in payload:
            _ensure(isinstance(payload["title"], str) and len(payload["title"]) <= 120, "title invalid")


def validate_job(job: dict[str, Any]) -> None:
    if jsonschema is not None:
        jsonschema.validate(instance=job, schema=_load_schema("job.schema.json"))
        return
    _validate_job_lite(job)


def validate_payload_for_job_type(job_type: str, payload: dict[str, Any]) -> None:
    schema_name = {
        "repo_index_task": "repo_index_task.schema.json",
        "test_runner_task": "test_runner_task.schema.json",
        "doc_compactor_task": "doc_compactor_task.schema.json",
    }.get(job_type)
    if not schema_name:
        raise ValidationError(f"unsupported job_type {job_type}")

    if jsonschema is not None:
        jsonschema.validate(instance=payload, schema=_load_schema(schema_name))
        return
    _validate_schema_lite(schema_name, payload)
