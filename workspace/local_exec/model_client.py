from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class ModelClientError(RuntimeError):
    pass


class OpenAICompatClient:
    def __init__(self, base_url: str, model: str, api_key: str | None = None, timeout_sec: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_sec = timeout_sec

    def _stub(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        content = "stub-response"
        if messages:
            content = f"stub:{messages[-1].get('content', '')}"[:120]
        return {
            "id": "stub-local-exec",
            "choices": [{"message": {"content": content, "tool_calls": []}}],
            "usage": {"total_tokens": 0},
            "stub": True,
        }

    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "none",
        parallel_tool_calls: bool = False,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        if os.environ.get("OPENCLAW_LOCAL_EXEC_MODEL_STUB", "1") == "1" or not self.base_url:
            return self._stub(messages)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "tool_choice": tool_choice,
            "parallel_tool_calls": parallel_tool_calls,
        }
        if tools is not None:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:  # pragma: no cover - network path optional
            raise ModelClientError(str(exc)) from exc

        return json.loads(body)


def reject_disallowed_tool_calls(tool_calls: list[dict[str, Any]], allowed_tools: set[str]) -> None:
    for call in tool_calls:
        fn_name = (((call or {}).get("function") or {}).get("name"))
        if fn_name and fn_name not in allowed_tools:
            raise ModelClientError(f"disallowed_tool_call:{fn_name}")
