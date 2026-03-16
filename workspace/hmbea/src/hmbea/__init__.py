"""HMBEA - Hierarchical Multi-Being Evolutionary Architecture"""
import json
import yaml
from pathlib import Path
import requests


LLAMA_CPP_URL = "http://localhost:8001/v1/chat/completions"
MODEL = "local-assistant"


def _call_llama(system: str, user: str) -> str:
    """Call local llama.cpp server."""
    response = requests.post(LLAMA_CPP_URL, json={
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }, timeout=180)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _classify_task(request: str) -> dict:
    """Classify incoming task."""
    lower = request.lower()
    
    if any(k in lower for k in ["code", "implement", "fix", "bug", "refactor", "function", "python", "script"]):
        task_type = "code"
    elif any(k in lower for k in ["research", "find", "search", "analyze", "explain"]):
        task_type = "research"
    else:
        task_type = "general"
    
    if any(k in lower for k in ["complex", "architect", "design", "audit"]):
        difficulty = "high"
    elif any(k in lower for k in ["simple", "quick"]):
        difficulty = "low"
    else:
        difficulty = "medium"
    
    return {"type": task_type, "difficulty": difficulty}


def run(request: str) -> dict:
    """Run a task through HMBEA pipeline."""
    # 1. Intake - classify task
    task = _classify_task(request)
    
    # 2. Retrieve - get context (placeholder)
    context = [{"source": "task", "content": request}]
    
    # 3. Execute - call LLM
    system = """You are a capable AI assistant. Provide clear, accurate responses."""
    user = f"Task: {request}\nType: {task['type']}\nDifficulty: {task['difficulty']}\n\nProvide your response."
    
    try:
        response = _call_llama(system, user)
        answer = response
        confidence = 0.7  # Assume good for now
    except Exception as e:
        answer = f"Error: {e}"
        confidence = 0.0
    
    # 4. Validate - simple check
    groundedness = 0.7 if len(answer) > 50 else 0.5
    
    # 5. Gate - decide
    if confidence >= 0.75:
        escalated = False
        decision = "accept"
    elif confidence >= 0.5:
        escalated = False
        decision = "retry"
    else:
        escalated = True
        decision = "escalate"
    
    return {
        "answer": answer,
        "task_type": task["type"],
        "difficulty": task["difficulty"],
        "confidence": confidence,
        "groundedness": groundedness,
        "decision": decision,
        "escalated": escalated,
    }


if __name__ == "__main__":
    import sys
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello"
    result = run(task)
    print(json.dumps(result, indent=2))
