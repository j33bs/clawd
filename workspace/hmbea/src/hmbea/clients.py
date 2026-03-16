"""HMBEA OpenAI-Compatible Clients"""
import json
import requests


class OpenAICompatibleClient:
    """Client for OpenAI-compatible APIs (llama.cpp, vLLM, etc.)"""
    
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
    
    def chat(self, system: str, user: str, **kwargs) -> str:
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
        resp = requests.post(url, json=payload, timeout=180)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    
    def chat_json(self, system: str, user: str, schema: type = None) -> dict:
        """Send chat request expecting JSON response."""
        url = f"{self.base_url}/chat/completions"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        
        # Try JSON mode
        payload["response_format"] = {"type": "json_object"}
        
        resp = requests.post(url, json=payload, timeout=180)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        
        try:
            return json.loads(content)
        except:
            return {"answer": content, "confidence": 0.5}
