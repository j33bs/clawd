#!/usr/bin/env python3
"""
Message Load Balancer - Routes messages between MiniMax and ChatGPT based on load.

When MiniMax is overwhelmed (too many concurrent messages or high latency),
automatically falls back to spawning a ChatGPT subagent to handle overflow.
"""

import os
import time
import json
import threading
from datetime import datetime, timezone
from typing import Any, Optional
from dataclasses import dataclass, field

# Configurable thresholds
MAX_QUEUE_DEPTH = int(os.environ.get("MAX_QUEUE_DEPTH", "5"))
MAX_LATENCY_MS = int(os.environ.get("MAX_LATENCY_MS", "30000"))
ENABLE_FALLBACK = os.environ.get("ENABLE_FALLBACK", "true").lower() == "true"


@dataclass
class LoadMetrics:
    """Current system load metrics."""
    queue_depth: int = 0
    avg_latency_ms: float = 0
    active_agents: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Message:
    """A message to be processed."""
    id: str
    content: str
    sender: str
    timestamp: str
    priority: str = "normal"
    assigned_agent: Optional[str] = None


class LoadBalancer:
    """Routes messages between MiniMax and ChatGPT based on load."""
    
    def __init__(self):
        self.metrics = LoadMetrics()
        self.message_queue: list[Message] = []
        self.fallback_log: list[dict] = []
        self._lock = threading.Lock()
    
    def update_metrics(self, queue_depth: int, avg_latency_ms: float, active_agents: int):
        """Update current load metrics."""
        with self._lock:
            self.metrics.queue_depth = queue_depth
            self.metrics.avg_latency_ms = avg_latency_ms
            self.metrics.active_agents = active_agents
            self.metrics.timestamp = datetime.now(timezone.utc).isoformat()
    
    def check_overload(self) -> bool:
        """Check if MiniMax is overwhelmed and needs fallback."""
        if not ENABLE_FALLBACK:
            return False
        
        with self._lock:
            queue_overload = self.metrics.queue_depth >= MAX_QUEUE_DEPTH
            latency_overload = self.metrics.avg_latency_ms >= MAX_LATENCY_MS
        
        return queue_overload or latency_overload
    
    def should_route_to_chatgpt(self) -> bool:
        """Determine if new messages should go to ChatGPT instead of MiniMax."""
        return self.check_overload()
    
    def route_message(self, message: Message) -> dict[str, Any]:
        """Route a message to the appropriate agent."""
        route_to_chatgpt = self.should_route_to_chatgpt()
        
        decision = {
            "message_id": message.id,
            "route": "chatgpt" if route_to_chatgpt else "minimax",
            "reason": self._get_route_reason(route_to_chatgpt),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "queue_depth": self.metrics.queue_depth,
                "avg_latency_ms": self.metrics.avg_latency_ms,
            }
        }
        
        # Log fallback events
        if route_to_chatgpt:
            self._log_fallback(message, decision)
        
        return decision
    
    def _get_route_reason(self, route_to_chatgpt: bool) -> str:
        """Get human-readable reason for routing decision."""
        if not route_to_chatgpt:
            return "Normal load - MiniMax available"
        
        reasons = []
        if self.metrics.queue_depth >= MAX_QUEUE_DEPTH:
            reasons.append(f"Queue depth ({self.metrics.queue_depth}) >= threshold ({MAX_QUEUE_DEPTH})")
        if self.metrics.avg_latency_ms >= MAX_LATENCY_MS:
            reasons.append(f"Latency ({self.metrics.avg_latency_ms}ms) >= threshold ({MAX_LATENCY_MS}ms)")
        
        return "; ".join(reasons) or "Load threshold exceeded"
    
    def _log_fallback(self, message: Message, decision: dict):
        """Log fallback event for auditing."""
        self.fallback_log.append({
            "message_id": message.id,
            "timestamp": decision["timestamp"],
            "reason": decision["reason"],
            "routed_to": decision["route"],
            "sender": message.sender,
        })
        
        # Keep only last 1000 events
        if len(self.fallback_log) > 1000:
            self.fallback_log = self.fallback_log[-1000:]
    
    def get_status(self) -> dict:
        """Get current load balancer status."""
        with self._lock:
            return {
                "enabled": ENABLE_FALLBACK,
                "overloaded": self.check_overload(),
                "metrics": {
                    "queue_depth": self.metrics.queue_depth,
                    "avg_latency_ms": self.metrics.avg_latency_ms,
                    "active_agents": self.metrics.active_agents,
                },
                "config": {
                    "max_queue_depth": MAX_QUEUE_DEPTH,
                    "max_latency_ms": MAX_LATENCY_MS,
                },
                "fallback_count": len(self.fallback_log),
                "recent_fallbacks": self.fallback_log[-10:] if self.fallback_log else [],
            }


# Global instance
_load_balancer: Optional[LoadBalancer] = None


def get_load_balancer() -> LoadBalancer:
    """Get or create the global load balancer instance."""
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = LoadBalancer()
    return _load_balancer


def check_load() -> bool:
    """Check if system is overloaded. Use this in your message handler."""
    return get_load_balancer().check_overload()


def route_message(message: dict) -> dict:
    """Route a message. Returns routing decision with agent to use."""
    msg = Message(
        id=message.get("id", str(time.time())),
        content=message.get("content", ""),
        sender=message.get("sender", "unknown"),
        timestamp=message.get("timestamp", datetime.now(timezone.utc).isoformat()),
        priority=message.get("priority", "normal"),
    )
    return get_load_balancer().route_message(msg)


def spawn_chatgpt_subagent(task: str, context: dict = None) -> dict:
    """
    Spawn a ChatGPT subagent to handle overflow.
    
    This uses OpenClaw's sessions_spawn internally. In production,
    you'd call this when route_message() returns route: "chatgpt".
    
    Returns spawn result with session_key.
    """
    # This would integrate with OpenClaw's API
    # For now, returns the parameters you'd need
    return {
        "action": "spawn",
        "agentId": "main",
        "model": "openai-codex/gpt-5.3-codex",
        "task": task,
        "context": context or {},
        "note": "Spawned due to MiniMax overload",
    }


def main():
    """CLI for testing the load balancer."""
    import sys
    
    lb = get_load_balancer()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            print(json.dumps(lb.get_status(), indent=2))
        elif sys.argv[1] == "simulate":
            # Simulate some load
            for i in range(10):
                msg = {
                    "id": f"msg-{i}",
                    "content": f"Test message {i}",
                    "sender": f"user-{i}",
                }
                decision = route_message(msg)
                print(f"Message {i}: {decision['route']} ({decision['reason']})")
        else:
            print("Usage: message_load_balancer.py [status|simulate]")
    else:
        print("Message Load Balancer")
        print(f"  Max Queue Depth: {MAX_QUEUE_DEPTH}")
        print(f"  Max Latency: {MAX_LATENCY_MS}ms")
        print(f"  Fallback Enabled: {ENABLE_FALLBACK}")
        print(f"\nRun with 'status' or 'simulate'")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
