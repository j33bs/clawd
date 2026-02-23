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
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal test environments
    aiohttp = None

from event_envelope import append_envelope, make_envelope
from pairing_preflight import ensure_pairing_healthy

# Configuration
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:18789")
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")  # Set your token
MAX_QUEUE_DEPTH = int(os.environ.get("MAX_QUEUE_DEPTH", "5"))
MAX_LATENCY_MS = int(os.environ.get("MAX_LATENCY_MS", "30000"))


def _event_log_path() -> Path:
    return Path(
        os.environ.get("OPENCLAW_EVENT_ENVELOPE_LOG_PATH")
        or (Path.home() / ".local" / "share" / "openclaw" / "events" / "gate_health.jsonl")
    ).expanduser()


def _append_gate_event(corr_id: str, severity: str, details: dict) -> dict:
    event = make_envelope(
        event="subagent.spawn.blocked",
        severity=severity,
        component="message_handler",
        corr_id=corr_id,
        details=details,
    )
    return append_envelope(_event_log_path(), event)


def _build_pairing_error(corr_id: str, preflight: dict) -> dict:
    reason = str(preflight.get("reason") or "PAIRING_REMEDIATION_FAILED")
    return {
        "ok": False,
        "error": {
            "type": "PAIRING_UNHEALTHY",
            "tier": "LOCAL",
            "confidence": 0.9,
            "corr_id": corr_id,
            "reason": reason,
            "remediation": [
                str(preflight.get("remedy") or ""),
                "run `workspace/scripts/check_gateway_pairing_health.sh`",
                "run `openclaw pairing list --json`",
            ],
            "observations": preflight.get("observations", {}),
        },
    }


def _is_pairing_error_response(payload: dict) -> bool:
    text = json.dumps(payload or {}, ensure_ascii=True).lower()
    return "pairing required" in text or "\"code\":1008" in text or "\"type\":\"pairing_unhealthy\"" in text


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
    if aiohttp is None:
        raise RuntimeError("aiohttp is required for Telegram reply dispatch")
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


async def _spawn_once(payload: dict, gateway_url: str, token: str) -> dict:
    if aiohttp is None:
        raise RuntimeError("aiohttp is required for subagent spawn")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{gateway_url}/api/agents/spawn",
            json=payload,
            headers=headers
        ) as resp:
            return await resp.json()


async def spawn_chatgpt_subagent(task: str, context: dict, gateway_url: str, token: str):
    """Spawn a ChatGPT subagent to handle a message.
    
    Uses OpenClaw's sessions_spawn internally.
    """
    corr_id = str((context or {}).get("corr_id") or f"spawn_{uuid.uuid4().hex[:12]}")
    preflight = ensure_pairing_healthy(corr_id=corr_id)
    if not preflight.get("ok"):
        _append_gate_event(
            corr_id,
            "ERROR",
            {
                "reason": preflight.get("reason"),
                "remedy": preflight.get("remedy"),
            },
        )
        return _build_pairing_error(corr_id, preflight)

    payload = {
        "agentId": "main",
        "model": "openai-codex/gpt-5.3-codex",
        "task": task,
        "context": {**(context or {}), "corr_id": corr_id},
        "timeoutSeconds": 120
    }

    result = await _spawn_once(payload, gateway_url, token)
    if _is_pairing_error_response(result) and preflight.get("safe_to_retry_now"):
        retry_corr = f"{corr_id}_retry"
        retry_preflight = ensure_pairing_healthy(corr_id=retry_corr)
        if retry_preflight.get("ok"):
            return await _spawn_once(payload, gateway_url, token)
        _append_gate_event(
            retry_corr,
            "WARN",
            {
                "reason": retry_preflight.get("reason"),
                "remedy": retry_preflight.get("remedy"),
            },
        )
        return _build_pairing_error(retry_corr, retry_preflight)
    if _is_pairing_error_response(result):
        _append_gate_event(
            corr_id,
            "WARN",
            {
                "reason": "PAIRING_REMOTE_REQUIRED",
                "remedy": "run `openclaw pairing list --json` and retry spawn",
            },
        )
        return _build_pairing_error(
            corr_id,
            {
                "reason": "PAIRING_REMOTE_REQUIRED",
                "remedy": "run `openclaw pairing list --json` and retry spawn",
                "observations": {"spawn_response": "pairing_required"},
            },
        )
    return result


async def handle_incoming_message(message: dict, handler: MessageHandler) -> dict:
    """Process an incoming message with load balancing."""
    
    # Route message
    route = await handler.route_message(message)
    
    # Get message content
    content = message.get("content", "")
    message_id = message.get("message_id")
    chat_id = message.get("chat_id")
    
    # Apply prompt caching
    cached_prompt = handler.cache_prompt(content)
    
    # Get conversation context
    history = handler.message_history[-10:]  # Last 10 messages
    context = handler.summarize_context(history)
    
    # Build full prompt
    full_prompt = context + f"\n\nUser: {content}" if context else content
    
    if route["route"] == "chatgpt":
        # Spawn ChatGPT subagent
        result = await spawn_chatgpt_subagent(
            task=full_prompt,
            context={"original_message": message},
            gateway_url=GATEWAY_URL,
            token=GATEWAY_TOKEN
        )
        if result.get("ok") is False and isinstance(result.get("error"), dict):
            reason = str(result["error"].get("reason") or "PAIRING_UNHEALTHY")
            reply_text = f"Temporary routing hold ({reason}). Please retry shortly."
        else:
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
