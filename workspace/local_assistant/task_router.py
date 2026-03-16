#!/usr/bin/env python3
"""
Task Router for Local Assistant (Qwen3.5-27B)
Routes tasks to local model based on capability demonstration
"""

import json
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

REPO_ROOT = Path("/home/jeebs/src/clawd")
LOCAL_MODEL_URL = "http://127.0.0.1:8001/v1/chat/completions"
LOCAL_MODEL_NAME = "local-assistant"

# Capability levels - expand as model demonstrates competence
CAPABILITY_LEVELS = {
    "level_1": {
        "description": "Basic Q&A, simple tasks",
        "max_tokens": 2048,
        "tasks": ["echo", "summarize", "classify"]
    },
    "level_2": {
        "description": "Code review, documentation",
        "max_tokens": 4096,
        "tasks": ["code_review", "docs", "refactor"]
    },
    "level_3": {
        "description": "Complex reasoning, agentic tasks",
        "max_tokens": 8192,
        "tasks": ["plan", "decompose", "execute"]
    }
}

def check_local_model() -> bool:
    """Verify local model is responding"""
    try:
        resp = requests.get("http://127.0.0.1:8001/v1/models", timeout=5)
        return resp.status_code == 200
    except:
        return False

def chat_local(prompt: str, system: str = None, max_tokens: int = 2048, temperature: float = 0.7) -> Optional[str]:
    """Send prompt to local Qwen3.5-27B"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    try:
        resp = requests.post(
            LOCAL_MODEL_URL,
            json={
                "model": LOCAL_MODEL_NAME,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            },
            timeout=120
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Local model error: {e}")
    return None

def route_task(prompt: str, task_type: str = "general", force_local: bool = False) -> dict:
    """
    Route task to appropriate model.
    Returns {"model": "local|remote", "response": str, "latency_ms": float}
    """
    from time import time
    start = time()
    
    # Determine capability level
    level = "level_1"
    for lvl, cfg in CAPABILITY_LEVELS.items():
        if task_type in cfg["tasks"]:
            level = lvl
            break
    
    max_tokens = CAPABILITY_LEVELS[level]["max_tokens"]
    
    # Try local first if available
    if check_local_model():
        response = chat_local(prompt, max_tokens=max_tokens)
        if response:
            return {
                "model": "local",
                "response": response,
                "latency_ms": int((time() - start) * 1000),
                "capability_level": level,
                "task_type": task_type
            }
    
    # Fallback to remote (require explicit opt-in for now)
    if force_local:
        return {"model": "local", "response": None, "error": "local unavailable"}
    
    # Return instruction to use remote
    return {
        "model": "remote_needed",
        "instruction": f"Task type: {task_type}, Level: {level}",
        "prompt": prompt
    }

# Simple CLI
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            print(f"Local model: {'ONLINE' if check_local_model() else 'OFFLINE'}")
            print(f"Capability levels: {len(CAPABILITY_LEVELS)}")
        elif sys.argv[1] == "test":
            result = chat_local("Say 'Hello from Qwen3.5-27B' in exactly 5 words")
            print(f"Test response: {result}")
        else:
            prompt = " ".join(sys.argv[1:])
            result = route_task(prompt)
            print(json.dumps(result, indent=2))
