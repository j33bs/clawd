#!/usr/bin/env python3
"""CEL smart session spawn wrapper with deterministic logging."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREPARED_PATH = REPO_ROOT / "workspace" / "runtime" / "codex_prepared_prompt.json"
DEFAULT_LOG_PATH = REPO_ROOT / "workspace" / "runtime" / "codex_sessions.log"
DEFAULT_GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:18789")
DEFAULT_GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")
DEFAULT_AGENT_ID = "main"
DEFAULT_DRAFT_MODEL = os.environ.get("OPENCLAW_CODEX_DRAFT_MODEL", "openai-codex/gpt-5.3-codex-spark")
DEFAULT_FULL_MODEL = os.environ.get("OPENCLAW_CODEX_FULL_MODEL", "openai-codex/gpt-5.3-codex")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid JSON object in {path}")
    return data


def _parse_context_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("--context-json must decode to a JSON object")
    return data


def _should_escalate(prepared: dict[str, Any], *, explicit_escalate: bool) -> bool:
    if explicit_escalate:
        return True
    constraints = str(prepared.get("sections", {}).get("CONSTRAINTS", "")).lower()
    if "escalate" in constraints and "codex" in constraints:
        return True
    if "full_codex" in constraints or "full codex" in constraints:
        return True
    return False


def select_model(
    prepared: dict[str, Any],
    *,
    model_override: str | None,
    explicit_escalate: bool,
) -> str:
    if model_override:
        return model_override
    return DEFAULT_FULL_MODEL if _should_escalate(prepared, explicit_escalate=explicit_escalate) else DEFAULT_DRAFT_MODEL


def build_attachments(prepared: dict[str, Any], *, max_files: int = 6, excerpt_chars: int = 1200) -> list[dict[str, Any]]:
    refs = prepared.get("referenced_files")
    if not isinstance(refs, list):
        return []

    out: list[dict[str, Any]] = []
    for item in refs:
        if len(out) >= max_files:
            break
        if not isinstance(item, dict):
            continue
        path_raw = item.get("path")
        if not isinstance(path_raw, str) or not path_raw.strip():
            continue
        path = Path(path_raw)
        if not path.exists() or not path.is_file():
            continue

        row: dict[str, Any] = {
            "path": str(path),
            "size_bytes": item.get("size_bytes"),
            "sha256": item.get("sha256"),
        }
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            row["excerpt"] = text[:excerpt_chars]
        except OSError:
            row["excerpt"] = ""
        out.append(row)

    return out


def _http_post_json(
    url: str,
    payload: dict[str, Any],
    *,
    token: str,
    timeout_seconds: int,
) -> tuple[int, Any]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        url,
        method="POST",
        headers=headers,
        data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw": body}
            return int(resp.getcode()), parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return int(getattr(exc, "code", 500) or 500), parsed


def append_session_log(log_path: Path, row: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def spawn_codex_session(
    *,
    prepared_prompt_path: Path,
    gateway_url: str,
    gateway_token: str,
    agent_id: str = DEFAULT_AGENT_ID,
    model_override: str | None = None,
    explicit_escalate: bool = False,
    timeout_seconds: int | None = None,
    thread: bool = True,
    mode: str = "session",
    dry_run: bool = False,
    context_overrides: dict[str, Any] | None = None,
    log_path: Path = DEFAULT_LOG_PATH,
) -> dict[str, Any]:
    prepared = _load_json(prepared_prompt_path)
    selected_model = select_model(
        prepared,
        model_override=model_override,
        explicit_escalate=explicit_escalate,
    )
    token_baseline = int(prepared.get("metadata", {}).get("token_estimate") or 0)
    task_hash = str(prepared.get("metadata", {}).get("task_hash") or "")

    attachments = build_attachments(prepared)
    cel_context = {
        "enabled": True,
        "version": "cel.v1",
        "prepared_prompt_path": str(prepared_prompt_path),
        "task_hash": task_hash,
        "token_baseline": token_baseline,
        "attachments": attachments,
    }

    merged_context = dict(context_overrides or {})
    merged_context["cel"] = cel_context

    payload: dict[str, Any] = {
        "agentId": agent_id,
        "model": selected_model,
        "task": str(prepared.get("normalized_prompt") or ""),
        "context": merged_context,
        "thread": bool(thread),
        "mode": str(mode or "session"),
    }
    if timeout_seconds is not None:
        payload["timeoutSeconds"] = int(timeout_seconds)

    if dry_run:
        response_payload: dict[str, Any] = {
            "ok": True,
            "dry_run": True,
            "session_id": f"dryrun-{uuid.uuid4().hex[:10]}",
            "request": payload,
        }
        status_code = 200
    else:
        endpoint = f"{gateway_url.rstrip('/')}/api/agents/spawn"
        status_code, response = _http_post_json(
            endpoint,
            payload,
            token=gateway_token,
            timeout_seconds=int(timeout_seconds or 120),
        )
        response_payload = {
            "ok": status_code < 400,
            "dry_run": False,
            "status_code": status_code,
            "response": response,
            "request": {
                "agentId": payload.get("agentId"),
                "model": payload.get("model"),
                "thread": payload.get("thread"),
                "mode": payload.get("mode"),
                "timeoutSeconds": payload.get("timeoutSeconds"),
            },
        }

    session_id = None
    if isinstance(response_payload.get("response"), dict):
        response_map = response_payload["response"]
        session_id = (
            response_map.get("session_id")
            or response_map.get("sessionId")
            or response_map.get("id")
            or response_map.get("key")
        )
    if response_payload.get("dry_run"):
        session_id = response_payload.get("session_id")

    log_row = {
        "timestamp": utc_now_iso(),
        "model": selected_model,
        "token_baseline": token_baseline,
        "task_hash": task_hash,
        "session_id": session_id,
        "prepared_prompt": str(prepared_prompt_path),
        "dry_run": bool(dry_run),
    }
    append_session_log(log_path, log_row)

    response_payload["log"] = log_row
    return response_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spawn Codex session via CEL wrapper")
    parser.add_argument("--prepared", default=str(DEFAULT_PREPARED_PATH), help="Prepared prompt artifact JSON")
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL, help="Gateway base URL")
    parser.add_argument("--token", default=DEFAULT_GATEWAY_TOKEN, help="Gateway bearer token")
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID, help="Target agent ID")
    parser.add_argument("--model", default="", help="Override model")
    parser.add_argument("--timeout-seconds", type=int, default=0, help="Spawn timeout seconds")
    parser.add_argument("--mode", default="session", help="Session mode (default: session)")
    parser.add_argument("--thread", action="store_true", default=True, help="Spawn persistent thread=true")
    parser.add_argument("--no-thread", dest="thread", action="store_false", help="Disable persistent thread")
    parser.add_argument("--escalate", action="store_true", help="Escalate to full Codex model")
    parser.add_argument("--context-json", default="", help="Optional JSON object merged into spawn context")
    parser.add_argument("--dry-run", action="store_true", help="Do not call gateway; emit synthetic spawn")
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH), help="Session log JSONL path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prepared_path = Path(args.prepared).expanduser().resolve()
    log_path = Path(args.log_path).expanduser().resolve()

    if not prepared_path.exists() or not prepared_path.is_file():
        print(json.dumps({"ok": False, "error": f"prepared prompt artifact not found: {prepared_path}"}, ensure_ascii=True))
        return 2

    try:
        context_overrides = _parse_context_json(args.context_json)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"invalid --context-json: {exc}"}, ensure_ascii=True))
        return 2

    dry_run = bool(args.dry_run or _bool_env("OPENCLAW_CEL_SPAWN_DRY_RUN", False))

    try:
        result = spawn_codex_session(
            prepared_prompt_path=prepared_path,
            gateway_url=str(args.gateway_url),
            gateway_token=str(args.token),
            agent_id=str(args.agent_id),
            model_override=(str(args.model).strip() or None),
            explicit_escalate=bool(args.escalate),
            timeout_seconds=(int(args.timeout_seconds) if int(args.timeout_seconds or 0) > 0 else None),
            thread=bool(args.thread),
            mode=str(args.mode or "session"),
            dry_run=dry_run,
            context_overrides=context_overrides,
            log_path=log_path,
        )
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 1

    print(json.dumps(result, ensure_ascii=True))
    return 0 if bool(result.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
