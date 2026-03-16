# SKILL.md - Local Assistant Auto-Router

## Triggers
- Any coding or reasoning task that could be handled locally
- When user asks for code review, refactor, or explanation

## Behavior

### Auto-Route (Priority 1)
Before responding to any task that matches these patterns, try local model first:

```python
from workspace.local_assistant.task_router import check_local_model, chat_local, route_task

# Simple tasks → local
SIMPLE_PATTERNS = ["explain", "what is", "how does", "summarize", "review code", "refactor"]

if any(p in prompt.lower() for p in SIMPLE_PATTERNS) and check_local_model():
    local_response = chat_local(prompt)
    if local_response:
        # Return local response, no need to call remote
        return local_response
```

### Auto-Learn (Priority 2)
After every response, capture the interaction:

```python
from workspace.local_assistant.learning_pipeline import save_sample

# Determine task type
task_type = "general"
if "code" in prompt.lower() or "function" in prompt.lower():
    task_type = "coding"
elif "why" in prompt.lower() or "how" in prompt.lower():
    task_type = "reasoning"

# Save for future training
save_sample(instruction=prompt, response=response, context=system_prompt, task_type=task_type)
```

## Automation

### Cron Job: Daily Routing Audit
- Check local model health
- Review recent tasks that could have been local
- Update capability levels based on success rate

### Cron Job: Weekly Learning Review  
- Analyze collected samples
- Identify patterns where local model excels
- Suggest capability level expansions

## Implementation

Add to agent startup or heartbeat:
```python
# Auto-import for all sessions
import sys
sys.path.insert(0, "/home/jeebs/src/clawd/workspace")
from local_assistant.task_router import check_local_model, chat_local
from local_assistant.learning_pipeline import save_sample
```
