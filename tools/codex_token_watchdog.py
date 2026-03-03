#!/usr/bin/env python3
"""CEL token observability watchdog for Codex sessions."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS_PATH = REPO_ROOT / "workspace" / "runtime" / "token_metrics.jsonl"
DEFAULT_GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:18789")
DEFAULT_GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_get_json(url: str, *, token: str, timeout_seconds: int) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"raw": body}
            return int(resp.getcode()), payload
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}
        return int(getattr(exc, "code", 500) or 500), payload


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_total_tokens_from_usage(payload: Any) -> int | None:
    if not isinstance(payload, (dict, list)):
        return None

    total_key_names = {
        "total_tokens",
        "totalTokens",
        "token_count",
        "tokenCount",
        "tokens_total",
    }
    prompt_key_names = {"prompt_tokens", "promptTokens", "input_tokens", "inputTokens"}
    completion_key_names = {"completion_tokens", "completionTokens", "output_tokens", "outputTokens"}

    found_totals: list[int] = []
    prompt_vals: list[int] = []
    completion_vals: list[int] = []

    stack: list[Any] = [payload]
    seen_ids: set[int] = set()

    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            node_id = id(node)
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    stack.append(value)
                    continue
                if not isinstance(value, (int, float)):
                    continue
                int_value = int(value)
                if key in total_key_names:
                    found_totals.append(int_value)
                elif key in prompt_key_names:
                    prompt_vals.append(int_value)
                elif key in completion_key_names:
                    completion_vals.append(int_value)
                elif key == "tokens" and int_value >= 0:
                    found_totals.append(int_value)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    stack.append(item)

    if found_totals:
        return max(found_totals)
    if prompt_vals or completion_vals:
        return max(prompt_vals or [0]) + max(completion_vals or [0])
    return None


def fetch_status_payload(
    *,
    session_id: str,
    gateway_url: str,
    gateway_token: str,
    timeout_seconds: int,
    status_file: Path | None,
    status_endpoint: str | None,
) -> tuple[str, int, Any]:
    if status_file:
        payload = _load_json(status_file)
        return ("status_file", 200, payload)

    base = gateway_url.rstrip("/")
    encoded_id = urllib.parse.quote(session_id, safe="")

    candidate_paths = []
    if status_endpoint:
        path = status_endpoint.replace("{session_id}", encoded_id)
        candidate_paths.append(path)
    candidate_paths.extend(
        [
            f"/api/sessions/{encoded_id}/status",
            f"/api/session/status/{encoded_id}",
            f"/api/session/status?sessionId={encoded_id}",
            f"/api/session_status?sessionId={encoded_id}",
            "/api/status",
        ]
    )

    for path in candidate_paths:
        url = f"{base}{path}"
        code, payload = _http_get_json(url, token=gateway_token, timeout_seconds=timeout_seconds)
        if code < 400:
            return (url, code, payload)

    # Return the last attempted payload if everything failed.
    return (f"{base}{candidate_paths[-1]}", code, payload)


def append_metric(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch Codex session token usage")
    parser.add_argument("--session-id", required=True, help="Session identifier to monitor")
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL, help="Gateway base URL")
    parser.add_argument("--token", default=DEFAULT_GATEWAY_TOKEN, help="Gateway bearer token")
    parser.add_argument("--poll-seconds", type=float, default=10.0, help="Polling interval seconds")
    parser.add_argument("--iterations", type=int, default=1, help="Number of polls (0=infinite)")
    parser.add_argument("--spike-threshold", type=int, default=5000, help="Delta threshold for warnings")
    parser.add_argument("--metrics-path", default=str(DEFAULT_METRICS_PATH), help="Metrics JSONL path")
    parser.add_argument("--timeout-seconds", type=int, default=20, help="HTTP timeout seconds")
    parser.add_argument("--status-file", default="", help="Offline status fixture JSON")
    parser.add_argument("--status-endpoint", default="", help="Custom status endpoint path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metrics_path = Path(args.metrics_path).expanduser().resolve()
    status_file = Path(args.status_file).expanduser().resolve() if args.status_file else None

    previous_total: int | None = None
    iteration = 0
    exit_code = 0

    while True:
        iteration += 1
        source, status_code, payload = fetch_status_payload(
            session_id=str(args.session_id),
            gateway_url=str(args.gateway_url),
            gateway_token=str(args.token),
            timeout_seconds=max(1, int(args.timeout_seconds)),
            status_file=status_file,
            status_endpoint=(str(args.status_endpoint).strip() or None),
        )

        total_tokens = _extract_total_tokens_from_usage(payload)
        delta = None if previous_total is None or total_tokens is None else int(total_tokens - previous_total)
        spike = bool(delta is not None and delta > int(args.spike_threshold))

        row = {
            "timestamp": utc_now_iso(),
            "session_id": str(args.session_id),
            "source": source,
            "status_code": int(status_code),
            "total_tokens": total_tokens,
            "delta_tokens": delta,
            "spike_threshold": int(args.spike_threshold),
            "warning": "token_spike" if spike else None,
            "recommend_restart": bool(spike),
            "watchdog": "codex_token_watchdog",
            "iteration": iteration,
        }
        append_metric(metrics_path, row)
        print(json.dumps(row, ensure_ascii=True))

        if spike:
            exit_code = 0

        if total_tokens is not None:
            previous_total = total_tokens

        if int(args.iterations) > 0 and iteration >= int(args.iterations):
            break
        time.sleep(max(0.1, float(args.poll_seconds)))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
