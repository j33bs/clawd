#!/usr/bin/env python3
"""Finalize Codex session by exporting history/artifacts and terminating cleanly."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "workspace" / "runtime" / "codex_outputs"
DEFAULT_GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:18789")
DEFAULT_GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _http_json(
    method: str,
    url: str,
    *,
    token: str,
    timeout_seconds: int,
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, method=method.upper(), headers=headers, data=data)
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


def _extract_total_tokens(payload: Any) -> int | None:
    if not isinstance(payload, (dict, list)):
        return None

    keys_total = {"total_tokens", "totalTokens", "token_count", "tokenCount", "tokens_total"}
    keys_prompt = {"prompt_tokens", "promptTokens", "input_tokens", "inputTokens"}
    keys_completion = {"completion_tokens", "completionTokens", "output_tokens", "outputTokens"}

    totals: list[int] = []
    prompt_vals: list[int] = []
    completion_vals: list[int] = []
    stack: list[Any] = [payload]
    seen_ids: set[int] = set()

    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            marker = id(node)
            if marker in seen_ids:
                continue
            seen_ids.add(marker)
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    stack.append(value)
                    continue
                if not isinstance(value, (int, float)):
                    continue
                ivalue = int(value)
                if key in keys_total or key == "tokens":
                    totals.append(ivalue)
                elif key in keys_prompt:
                    prompt_vals.append(ivalue)
                elif key in keys_completion:
                    completion_vals.append(ivalue)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    stack.append(item)

    if totals:
        return max(totals)
    if prompt_vals or completion_vals:
        return max(prompt_vals or [0]) + max(completion_vals or [0])
    return None


def _extract_output_texts(payload: Any) -> list[str]:
    texts: list[str] = []
    if not isinstance(payload, (dict, list)):
        return texts

    candidate_keys = ("content", "text", "output", "message", "response")
    stack: list[Any] = [payload]
    seen_ids: set[int] = set()

    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            marker = id(node)
            if marker in seen_ids:
                continue
            seen_ids.add(marker)
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    stack.append(value)
                elif isinstance(value, str) and key in candidate_keys:
                    content = value.strip()
                    if content:
                        texts.append(content)
        elif isinstance(node, list):
            for item in node:
                stack.append(item)

    deduped: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _fetch_with_candidates(
    *,
    method: str,
    gateway_url: str,
    token: str,
    timeout_seconds: int,
    endpoint_candidates: list[str],
    payload: dict[str, Any] | None = None,
) -> tuple[str, int, Any]:
    base = gateway_url.rstrip("/")
    last_code = 599
    last_payload: Any = {"error": "not_attempted"}
    last_url = ""
    for path in endpoint_candidates:
        url = f"{base}{path}"
        last_url = url
        code, body = _http_json(method, url, token=token, timeout_seconds=timeout_seconds, payload=payload)
        if code < 400:
            return (url, code, body)
        last_code = code
        last_payload = body
    return (last_url, last_code, last_payload)


def resolve_history(
    *,
    session_id: str,
    gateway_url: str,
    token: str,
    timeout_seconds: int,
    history_file: Path | None,
    history_endpoint: str | None,
) -> tuple[str, int, Any]:
    if history_file:
        return ("history_file", 200, _load_json(history_file))

    encoded = urllib.parse.quote(session_id, safe="")
    candidates: list[str] = []
    if history_endpoint:
        candidates.append(history_endpoint.replace("{session_id}", encoded))
    candidates.extend(
        [
            f"/api/sessions/{encoded}/history",
            f"/api/session/history/{encoded}",
            f"/api/session/history?sessionId={encoded}",
            f"/api/sessions_history?sessionId={encoded}",
        ]
    )
    return _fetch_with_candidates(
        method="GET",
        gateway_url=gateway_url,
        token=token,
        timeout_seconds=timeout_seconds,
        endpoint_candidates=candidates,
        payload=None,
    )


def resolve_status(
    *,
    session_id: str,
    gateway_url: str,
    token: str,
    timeout_seconds: int,
    status_file: Path | None,
    status_endpoint: str | None,
) -> tuple[str, int, Any]:
    if status_file:
        return ("status_file", 200, _load_json(status_file))

    encoded = urllib.parse.quote(session_id, safe="")
    candidates: list[str] = []
    if status_endpoint:
        candidates.append(status_endpoint.replace("{session_id}", encoded))
    candidates.extend(
        [
            f"/api/sessions/{encoded}/status",
            f"/api/session/status/{encoded}",
            f"/api/session/status?sessionId={encoded}",
            f"/api/session_status?sessionId={encoded}",
        ]
    )
    return _fetch_with_candidates(
        method="GET",
        gateway_url=gateway_url,
        token=token,
        timeout_seconds=timeout_seconds,
        endpoint_candidates=candidates,
        payload=None,
    )


def terminate_session(
    *,
    session_id: str,
    gateway_url: str,
    token: str,
    timeout_seconds: int,
    terminate_endpoint: str | None,
) -> tuple[str, int, Any]:
    encoded = urllib.parse.quote(session_id, safe="")
    candidates: list[str] = []
    if terminate_endpoint:
        candidates.append(terminate_endpoint.replace("{session_id}", encoded))
    candidates.extend(
        [
            f"/api/sessions/{encoded}/terminate",
            f"/api/session/terminate/{encoded}",
            f"/api/session/terminate?sessionId={encoded}",
            "/api/agents/terminate",
        ]
    )

    base_payload = {"sessionId": session_id}
    return _fetch_with_candidates(
        method="POST",
        gateway_url=gateway_url,
        token=token,
        timeout_seconds=timeout_seconds,
        endpoint_candidates=candidates,
        payload=base_payload,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize Codex session and export outputs")
    parser.add_argument("--session-id", required=True, help="Session identifier")
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL, help="Gateway base URL")
    parser.add_argument("--token", default=DEFAULT_GATEWAY_TOKEN, help="Gateway bearer token")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Output root directory")
    parser.add_argument("--history-file", default="", help="Offline history fixture JSON")
    parser.add_argument("--status-file", default="", help="Offline status fixture JSON")
    parser.add_argument("--history-endpoint", default="", help="Custom history endpoint path")
    parser.add_argument("--status-endpoint", default="", help="Custom status endpoint path")
    parser.add_argument("--terminate-endpoint", default="", help="Custom terminate endpoint path")
    parser.add_argument("--timeout-seconds", type=int, default=20, help="HTTP timeout")
    parser.add_argument("--skip-terminate", action="store_true", help="Do not terminate session")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session_id = str(args.session_id)
    output_root = Path(args.output_root).expanduser().resolve()
    out_dir = output_root / session_id
    out_dir.mkdir(parents=True, exist_ok=True)

    history_file = Path(args.history_file).expanduser().resolve() if args.history_file else None
    status_file = Path(args.status_file).expanduser().resolve() if args.status_file else None

    history_source, history_code, history_payload = resolve_history(
        session_id=session_id,
        gateway_url=str(args.gateway_url),
        token=str(args.token),
        timeout_seconds=max(1, int(args.timeout_seconds)),
        history_file=history_file,
        history_endpoint=(str(args.history_endpoint).strip() or None),
    )
    status_source, status_code, status_payload = resolve_status(
        session_id=session_id,
        gateway_url=str(args.gateway_url),
        token=str(args.token),
        timeout_seconds=max(1, int(args.timeout_seconds)),
        status_file=status_file,
        status_endpoint=(str(args.status_endpoint).strip() or None),
    )

    outputs = _extract_output_texts(history_payload)
    total_tokens = _extract_total_tokens(status_payload)
    if total_tokens is None:
        total_tokens = _extract_total_tokens(history_payload)

    (out_dir / "history.json").write_text(json.dumps(history_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    (out_dir / "status.json").write_text(json.dumps(status_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    (out_dir / "outputs.txt").write_text("\n\n---\n\n".join(outputs) + ("\n" if outputs else ""), encoding="utf-8")

    terminate_source = None
    terminate_code = None
    terminate_payload: Any = None
    terminated = False

    if not bool(args.skip_terminate):
        terminate_source, terminate_code, terminate_payload = terminate_session(
            session_id=session_id,
            gateway_url=str(args.gateway_url),
            token=str(args.token),
            timeout_seconds=max(1, int(args.timeout_seconds)),
            terminate_endpoint=(str(args.terminate_endpoint).strip() or None),
        )
        terminated = bool((terminate_code or 500) < 400)
        (out_dir / "terminate.json").write_text(
            json.dumps(
                {
                    "source": terminate_source,
                    "status_code": terminate_code,
                    "payload": terminate_payload,
                },
                indent=2,
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )

    summary = {
        "session_id": session_id,
        "finalized_at": utc_now_iso(),
        "history_source": history_source,
        "history_status_code": history_code,
        "status_source": status_source,
        "status_status_code": status_code,
        "outputs_count": len(outputs),
        "total_tokens": total_tokens,
        "terminated": terminated,
        "terminate_source": terminate_source,
        "terminate_status_code": terminate_code,
        "output_dir": str(out_dir),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    ok = history_code < 400 and status_code < 400
    print(json.dumps({"ok": ok, **summary}, ensure_ascii=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
