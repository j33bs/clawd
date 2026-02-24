# Codex Task: Chat Load Balancer with Free Tier Fallback

## Context
When the main chat system becomes overwhelmed (high latency, errors, rate limits), automatically route to a simpler "free tier" agent that can handle basic requests without hitting paid service limits.

## Problem
- Primary agent (Claude/GPT) hits rate limits during high load
- Expensive models waste capacity on simple queries
- No fallback when main system struggles

## Solution
Implement a load balancer with three tiers:

### Tier 1: Free (Always Available)
- Local model (Ollama Qwen)
- Handles: simple questions, basic queries, status checks
- Fast, free, always online

### Tier 2: Standard (Default)
- Remote model (Claude/GPT)
- Handles: complex reasoning, code generation, analysis

### Tier 3: Overflow (Fallback)
- Another remote instance or local fallback
- Activated when Tier 2 is saturated

## Implementation

### File: `workspace/scripts/chat_load_balancer.py`

```python
class ChatLoadBalancer:
    """
    Routes chat requests to appropriate tier based on load.
    """

    def __init__(self):
        self.tiers = {
            "free": {"model": "qwen2.5:0.5b", "cost": 0, "max_tokens": 512},
            "standard": {"model": "claude-3-opus", "cost": 1, "max_tokens": 4096},
            "overflow": {"model": "claude-3-haiku", "cost": 0.3, "max_tokens": 2048},
        }
        self.current_load = {"free": 0, "standard": 0, "overflow": 0}
        self.error_counts = {"free": 0, "standard": 0, "overflow": 0}

    def select_tier(self, query_complexity: str) -> str:
        """
        Select appropriate tier based on query.
        """
        # Simple queries go to free tier
        if query_complexity == "simple":
            return "free"
        # Medium complexity: try standard, fallback to overflow
        elif query_complexity == "medium":
            if self.current_load["standard"] < 10:
                return "standard"
            return "overflow"
        # Complex: standard with overflow backup
        else:
            return "standard"

    def route(self, message: str, context: dict = None) -> dict:
        """
        Route message to appropriate tier.
        Returns response and tier used.
        """
        # Determine complexity
        complexity = self._assess_complexity(message)

        # Try selected tier
        tier = self.select_tier(complexity)
        try:
            response = self._call_tier(tier, message, context)
            self.current_load[tier] += 1
            return {"response": response, "tier": tier, "success": True}
        except Exception as e:
            self.error_counts[tier] += 1
            # Fallback to free tier
            if tier != "free":
                return self._fallback_to_free(message, context)
            raise

    def _assess_complexity(self, message: str) -> str:
        """
        Assess query complexity.
        Simple: status checks, basic questions, single facts
        Medium: explanations, multiple steps, code snippets
        Complex: multi-file analysis, architecture, research
        """
        simple_patterns = ["what is", "status", "how do i", "list", "show"]
        complex_patterns = ["analyze", "design", "architecture", "research", "compare"]

        msg_lower = message.lower()
        if any(p in msg_lower for p in complex_patterns):
            return "complex"
        elif any(p in msg_lower for p in simple_patterns):
            return "simple"
        return "medium"

    def _call_tier(self, tier: str, message: str, context: dict) -> dict:
        """
        Call the selected tier's model.
        """
        # TODO: Implement actual model calls
        # For now, return placeholder
        return {"text": f"Response from {tier} tier", "tier": tier}

    def _fallback_to_free(self, message: str, context: dict) -> dict:
        """
        Fallback to free tier when standard fails.
        """
        try:
            response = self._call_tier("free", message, context)
            return {"response": response, "tier": "free", "fallback": True, "success": True}
        except Exception as e:
            return {"error": str(e), "tier": "free", "fallback": True, "success": False}

    def get_stats(self) -> dict:
        """
        Return current load balancer statistics.
        """
        return {
            "load": self.current_load.copy(),
            "errors": self.error_counts.copy(),
            "total_requests": sum(self.current_load.values()),
        }
```

## Features to Implement

### 1. Load Detection
- Monitor response latency
- Track error rates per tier
- Detect rate limit errors (429)
- Count concurrent requests

### 2. Automatic Fallback
- If standard tier errors, auto-fallback to overflow
- If overflow errors, fallback to free
- Log all fallbacks for analysis

### 3. Complexity Scoring
- Keyword-based complexity detection
- Optional: Use local model to classify before routing
- Configurable thresholds

### 4. Cost Tracking
- Track requests per tier
- Calculate estimated cost savings
- Alert when free tier is overused

### 5. Health Checks
- Ping each tier periodically
- Mark tiers as unhealthy when failing
- Auto-recover when tier returns

## Integration Points

### Option A: Standalone Service
Run as separate process, agents call it via HTTP.

### Option B: OpenClaw Plugin
Integrate into message routing in `workspace/scripts/message_load_balancer.py` (already exists!)

### Option C: Agent-Level
Each agent checks load before calling external model.

## Files to Modify/Create
- `workspace/scripts/chat_load_balancer.py` — Main implementation
- `workspace/scripts/load_balancer_cli.py` — CLI for testing
- `workspace/tests/test_load_balancer.py` — Unit tests

## Success Criteria
1. Simple queries routed to free tier without errors
2. Fallback triggers within 2 seconds of detecting overload
3. < 1% failed requests when fallback works
4. Cost savings: 30%+ of requests handled by free tier

## Priority
- Tier selection logic (immediate)
- Fallback mechanism (immediate)
- Complexity scoring (high)
- Cost tracking (medium)
- Health checks (low)
