#!/usr/bin/env python3
"""Contract checks for DALI heavy node endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

from starlette.requests import Request

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.runtime.heavy_node.server import AnswerRequest, HintRequest, create_app


class StubRouter:
    def warmup(self):
        return {"hint": {"status": "ok", "latency_ms": 4, "model": "stub-hint", "backend": "stub"}}

    def health(self):
        return {
            "status": "ok",
            "models": {
                "hint": {"status": "ok", "model": "stub-hint", "latency_ms": 4},
                "answer": {"status": "ok", "model": "stub-answer", "latency_ms": 7},
            },
        }

    def run_role(self, *, role, prompt, max_tokens, temperature, mode):
        if role == "hint":
            # Intentionally looks like a full solution so hint_guard must shrink it.
            return {
                "text": "Here's the full solution:\nStep 1 do this\nStep 2 do that\n```python\nprint('too much')\n```",
                "tokens_in": 22,
                "tokens_out": 70,
                "latency_ms": 9,
                "model": "stub-hint",
                "backend": "stub",
            }
        return {
            "text": f"{role} ok",
            "tokens_in": 18,
            "tokens_out": 12,
            "latency_ms": 11,
            "model": f"stub-{role}",
            "backend": "stub",
        }


def run() -> int:
    app = create_app(router=StubRouter())
    route_by_path = {route.path: route.endpoint for route in app.routes if getattr(route, "path", None)}
    health_endpoint = route_by_path["/health"]
    hint_endpoint = route_by_path["/hint"]
    answer_endpoint = route_by_path["/answer"]

    health = health_endpoint()
    health_json = health.model_dump()
    assert health_json["status"] == "ok", health_json
    assert "models" in health_json and isinstance(health_json["models"], dict), health_json

    request = Request(
        {
            "type": "http",
            "headers": [],
            "client": ("127.0.0.1", 9999),
            "scheme": "http",
            "server": ("127.0.0.1", 18891),
            "method": "POST",
            "path": "/hint",
        }
    )
    hint = hint_endpoint(
        HintRequest(
            problem="Need a strategy for debugging recursion.",
            attempt="I only rerun tests.",
            budget_tokens=40,
            max_lines=4,
            mode="fast",
        ),
        request,
    )
    hint_json = hint.model_dump()
    lines = [line for line in hint_json["text"].splitlines() if line.strip()]
    assert hint_json["hint_only"] is True, hint_json
    assert 2 <= len(lines) <= 4, hint_json
    assert hint_json["tokens_out"] <= 40, hint_json

    answer = answer_endpoint(
        AnswerRequest(prompt="hello", max_tokens=64, temperature=0.2, mode="fast"),
        request,
    )
    answer_json = answer.model_dump()
    for key in ("text", "model", "backend", "latency_ms", "tokens_in", "tokens_out"):
        assert key in answer_json, answer_json

    print("PASS test_heavy_node_contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
