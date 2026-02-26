#!/usr/bin/env python3
"""
Message Handler with Load Balancing and Efficiency Optimizations

Integrates message_load_balancer with OpenClaw gateway for:
- Multi-chat response with ChatGPT fallback
- Reply-to-message threading
- Prompt caching
- Context summarization
"""

import os
import sys
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional
from agent_orchestration import build_default_orchestrator
from telegram_recall import inject_telegram_recall_context

# Configuration
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:18789")
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")  # Set your token
MAX_QUEUE_DEPTH = int(os.environ.get("MAX_QUEUE_DEPTH", "5"))
MAX_LATENCY_MS = int(os.environ.get("MAX_LATENCY_MS", "30000"))


class MessageHandler:
    """Handles messages with load balancing and efficiency optimizations."""
    
    def __init__(self, gateway_url: str, token: str):
        self.gateway_url = gateway_url
        self.token = token
        self.queue_depth = 0
        self.avg_latency = 0
        self.message_history = []  # For context summarization
        
    async def check_load(self) -> dict:
        """Check current system load."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.gateway_url}/api/status",
                    headers=self._auth_headers()
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Estimate queue depth from active sessions
                        sessions = data.get("sessions", {})
                        self.queue_depth = len(sessions.get("active", []))
                        return {
                            "overloaded": self.queue_depth >= MAX_QUEUE_DEPTH,
                            "queue_depth": self.queue_depth,
                            "latency": self.avg_latency
                        }
        except Exception as e:
            print(f"Load check failed: {e}")
        
        return {"overloaded": False, "queue_depth": 0, "latency": 0}
    
    async def route_message(self, message: dict) -> dict:
        """Route message to appropriate agent."""
        load = await self.check_load()
        
        # Determine routing
        if load["overloaded"]:
            route = "chatgpt"
            reason = f"Queue depth {load['queue_depth']} >= {MAX_QUEUE_DEPTH}"
        else:
            route = "minimax"
            reason = "Normal load"
        
        return {
            "route": route,
            "reason": reason,
            "message_id": message.get("message_id"),
            "chat_id": message.get("chat_id")
        }
    
    def _auth_headers(self) -> dict:
        """Get authorization headers."""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}
    
    def cache_prompt(self, prompt: str) -> str:
        """Add caching hints to prompt for API optimization.
        
        Put static context at the top - APIs cache the first portion.
        """
        # Static instructions that don't change
        static_context = """You are a helpful AI assistant. Be concise and accurate.
"""
        return static_context + prompt
    
    def summarize_context(self, history: list, max_tokens: int = 2000) -> str:
        """Summarize conversation history to save tokens.
        
        Keeps the most recent context while summarizing older messages.
        """
        if not history:
            return ""
        
        # Keep last N messages, summarize the rest
        keep_recent = 5
        recent = history[-keep_recent:]
        older = history[:-keep_recent]
        
        summary = f"[Earlier conversation summarized from {len(older)} messages]"
        
        if older:
            # Simple summarization - just count messages by role
            roles = {}
            for msg in older:
                role = msg.get("role", "unknown")
                roles[role] = roles.get(role, 0) + 1
            summary += f" ({roles.get('user', 0)} user messages, {roles.get('assistant', 0)} assistant responses)"
        
        # Build context
        context = summary + "\n\nRecent messages:\n"
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:200]  # Truncate long messages
            context += f"{role}: {content}\n"
        
        return context


async def send_telegram_reply(chat_id: str, message_id: str, text: str, gateway_url: str, token: str):
    """Send a Telegram reply to a specific message."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    payload = {
        "action": "send",
        "channel": "telegram",
        "target": chat_id,
        "message": text,
        "replyTo": message_id  # This makes it a threaded reply
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{gateway_url}/api/tool/message",
            json=payload,
            headers=headers
        ) as resp:
            return await resp.json()


async def spawn_chatgpt_subagent(task: str, context: dict, gateway_url: str, token: str):
    """Spawn a ChatGPT subagent to handle a message.
    
    Uses OpenClaw's sessions_spawn internally.
    """
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    orchestrator = build_default_orchestrator()
    spawn_plan = orchestrator.prepare_spawn(
        task=task,
        context=context or {},
        priority=(context or {}).get("priority", "normal"),
        specialization_tags=(context or {}).get("specialization_tags"),
        providers=["openai-codex/gpt-5.3-codex"],
        enqueue_if_busy=False,
    )

    handoff_id = None
    if (context or {}).get("handoff_from_agent") and (context or {}).get("handoff_to_agent"):
        handoff_id = orchestrator.create_handoff(
            str(context.get("handoff_from_agent")),
            str(context.get("handoff_to_agent")),
            str(context.get("handoff_summary") or "spawn request handoff"),
            payload={"task_preview": task[:200]},
        )

    payload = {
        "agentId": "main",
        "model": spawn_plan["provider"],
        "task": task,
        "context": {
            **(context or {}),
            "specializationTags": spawn_plan["specialization_tags"],
            **({"handoffId": handoff_id} if handoff_id else {}),
        },
        "timeoutSeconds": spawn_plan["timeout_seconds"]
    }

    run_id = orchestrator.register_run_start(
        agent_id="main",
        provider=spawn_plan["provider"],
        request={"task_preview": task[:200], "priority": spawn_plan["priority"]},
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{gateway_url}/api/agents/spawn",
                json=payload,
                headers=headers
            ) as resp:
                result = await resp.json()
                status = "ok" if resp.status < 400 else "error"
                orchestrator.register_run_end(
                    run_id,
                    status=status,
                    state_update={"mood": str((context or {}).get("mood", "active"))},
                )
                if handoff_id and status == "ok":
                    orchestrator.acknowledge_handoff(handoff_id, "main", "spawn accepted")
                return result
    except Exception:
        orchestrator.register_run_end(run_id, status="error")
        raise


async def handle_incoming_message(message: dict, handler: MessageHandler) -> dict:
    """Process an incoming message with load balancing."""
    
    # Route message
    route = await handler.route_message(message)
    
    # Get message content
    content = message.get("content", "")
    message_id = message.get("message_id")
    chat_id = message.get("chat_id")
    session_start = bool(message.get("session_start", False))

    # Optional semantic recall hook from Telegram vector store (disabled by default).
    content_with_recall = inject_telegram_recall_context(
        str(content),
        env=os.environ,
        session_start=session_start,
    )
    
    # Apply prompt caching
    cached_prompt = handler.cache_prompt(content_with_recall)
    
    # Get conversation context
    history = handler.message_history[-10:]  # Last 10 messages
    context = handler.summarize_context(history)
    
    # Build full prompt
    full_prompt = context + f"\n\nUser: {content_with_recall}" if context else content_with_recall
    
    if route["route"] == "chatgpt":
        # Spawn ChatGPT subagent
        result = await spawn_chatgpt_subagent(
            task=full_prompt,
            context={"original_message": message},
            gateway_url=GATEWAY_URL,
            token=GATEWAY_TOKEN
        )
        
        reply_text = result.get("response", "Sorry, I couldn't process your request.")
    else:
        # Use MiniMax (normal flow) - would integrate with gateway here
        reply_text = f"[Would route to MiniMax] {content[:100]}..."
    
    # Send reply with threading (replyTo)
    if chat_id and message_id:
        await send_telegram_reply(
            chat_id=str(chat_id),
            message_id=str(message_id),
            text=reply_text,
            gateway_url=GATEWAY_URL,
            token=GATEWAY_TOKEN
        )
    
    # Update history
    handler.message_history.append({
        "role": "user",
        "content": content
    })
    handler.message_history.append({
        "role": "assistant", 
        "content": reply_text
    })
    
    return {
        "success": True,
        "route": route["route"],
        "reason": route["reason"]
    }


async def main():
    """Main entry point for testing."""
    handler = MessageHandler(GATEWAY_URL, GATEWAY_TOKEN)
    
    # Test message
    test_message = {
        "message_id": "123",
        "chat_id": "8159253715",
        "content": "Hello, this is a test message"
    }
    
    result = await handle_incoming_message(test_message, handler)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
