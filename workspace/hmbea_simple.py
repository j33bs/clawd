#!/usr/bin/env python3
"""Simple HMBEA - Uses existing local LLM"""
import requests

LLAMA_CPP_URL = "http://localhost:8001/v1/chat/completions"
MODEL = "local-assistant"


def run(task: str) -> dict:
    """Run task through local LLM."""
    response = requests.post(LLAMA_CPP_URL, json={
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": task}
        ]
    }, timeout=120)
    return {"answer": response.json()["choices"][0]["message"]["content"]}


if __name__ == "__main__":
    import sys
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello"
    print(run(task)["answer"])
