from __future__ import annotations

import json
import urllib.request
from typing import Any

from pydantic import BaseModel


class OpenAICompatibleClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat_json(self, *, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        """
        Minimal OpenAI-compatible JSON mode client.

        This intentionally avoids SDK coupling.
        Replace with the provider SDK of your choice if needed.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                },
            },
            "temperature": 0.1,
        }
        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"]
        return json.loads(text)
