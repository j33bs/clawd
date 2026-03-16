"""HMBEA OpenAI-Compatible Clients"""
import json
from typing import Any
import requests


class OpenAICompatibleClient:
    """Client for OpenAI-compatible APIs (llama.cpp, vLLM, etc.)"""
    
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
    
    def chat(self, system: str, user: str, **kwargs) -> dict:
        """Send chat completion request."""
        url = f"{self.base_url}/chat/completions"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            **kwargs
        }
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    
    def chat_json(self, system: str, user: str, schema: type) -> dict:
        """Send chat request expecting JSON response."""
        url = f"{self.base_url}/chat/completions"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"}
        }
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
