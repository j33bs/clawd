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
from pathlib import Path
from typing import Any, Optional
from agent_orchestration import build_default_orchestrator
from telegram_recall import inject_telegram_recall_context

# CEL tool imports are optional to preserve backward compatibility.
REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
try:
    from codex_prepare_prompt import build_prepared_prompt_payload, write_prepared_prompt_file
    from codex_spawn_session import spawn_codex_session
except Exception:  # pragma: no cover
    build_prepared_prompt_payload = None
    write_prepared_prompt_file = None
    spawn_codex_session = None

SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
try:
    from model_intent_router import maybe_apply_model_intent
except Exception:  # pragma: no cover
    maybe_apply_model_intent = None

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
    
    # Rolling history compaction constants
    _HISTORY_MAX_VERBATIM = 3       # last N messages kept verbatim
    _HISTORY_MAX_CHARS = 1600       # budget for compressed older-message summary (≈400 tokens)
    _CHARS_PER_TOKEN = 4.0

    def compact_history(self, history: list[dict]) -> list[dict]:
        """
        Rolling compaction: keep the last _HISTORY_MAX_VERBATIM messages verbatim,
        compress older messages to 1-line per-message summaries (role + first 80 chars).

        Replaces the coarse summarize_context() approach (message counts only).
        Saves 0–400 tokens per message when history depth > 3.
        Token budget for the summary block: ~400 tokens (_HISTORY_MAX_CHARS / 4).
        """
        if len(history) <= self._HISTORY_MAX_VERBATIM:
            return history

        recent = history[-self._HISTORY_MAX_VERBATIM:]
        older = history[:-self._HISTORY_MAX_VERBATIM]

        # Collapse each older message to a 1-line summary
        lines = []
        for msg in older:
            role = msg.get("role", "?")[:1].upper()   # U / A / S / T
            content = str(msg.get("content", "")).replace("\n", " ").strip()
            snippet = content[:80] + ("…" if len(content) > 80 else "")
            lines.append(f"[{role}] {snippet}")

        summary_text = "\n".join(lines)
        # Truncate if summary itself exceeds budget
        if len(summary_text) > self._HISTORY_MAX_CHARS:
            summary_text = summary_text[-self._HISTORY_MAX_CHARS:]

        summary_msg = {"role": "system", "content": f"[Prior context]\n{summary_text}"}
        return [summary_msg] + recent

    def summarize_context(self, history: list, max_tokens: int = 2000) -> str:
        """
        Build a summarized context string from history.
        Delegates to compact_history() for rolling compaction.
        Kept for backward compatibility with callers expecting a string return.
        """
        if not history:
            return ""
        compacted = self.compact_history(history)
        parts = []
        for msg in compacted:
            role = msg.get("role", "?")
            content = str(msg.get("content", ""))[:300]
            parts.append(f"{role}: {content}")
        return "\n".join(parts)


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

    payload_context = {
        **(context or {}),
        "specializationTags": spawn_plan["specialization_tags"],
        **({"handoffId": handoff_id} if handoff_id else {}),
    }

    payload = {
        "agentId": "main",
        "model": spawn_plan["provider"],
        "task": task,
        "context": payload_context,
        "timeoutSeconds": spawn_plan["timeout_seconds"]
    }

    run_id = orchestrator.register_run_start(
        agent_id="main",
        provider=spawn_plan["provider"],
        request={"task_preview": task[:200], "priority": spawn_plan["priority"]},
    )

    try:
        # Preferred path: CEL prepare+spawn wrapper for deterministic token discipline.
        cel_available = (
            callable(build_prepared_prompt_payload)
            and callable(write_prepared_prompt_file)
            and callable(spawn_codex_session)
        )
        if cel_available:
            runtime_dir = REPO_ROOT / "workspace" / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)

            prompt_text = "\n\n".join(
                [
                    "GOAL\nHandle the incoming message task via Codex session.",
                    (
                        "INPUTS\n"
                        f"- Task text:\n{task}\n"
                        f"- Context JSON:\n{json.dumps(payload_context, ensure_ascii=True, sort_keys=True)}\n"
                        "- workspace/scripts/message_handler.py"
                    ),
                    "OUTPUTS\n- A response payload suitable for gateway reply routing.",
                    "CONSTRAINTS\n- Preserve existing contracts and backwards compatibility.",
                    "SUCCESS_CRITERIA\n- Session spawn succeeds and returns structured response payload.",
                ]
            )
            prompt_path = runtime_dir / "codex_prompt_latest.md"
            prompt_path.write_text(prompt_text + "\n", encoding="utf-8")

            prepared_path = runtime_dir / "codex_prepared_prompt.json"
            prepared_payload = build_prepared_prompt_payload(
                prompt_text,
                source_path=prompt_path,
                cwd=REPO_ROOT,
            )
            write_prepared_prompt_file(prepared_path, prepared_payload)

            wrapped = spawn_codex_session(
                prepared_prompt_path=prepared_path,
                gateway_url=gateway_url,
                gateway_token=token,
                agent_id="main",
                model_override=str(spawn_plan["provider"]),
                timeout_seconds=int(spawn_plan["timeout_seconds"]),
                thread=True,
                mode="session",
                context_overrides=payload_context,
            )
            status = "ok" if bool(wrapped.get("ok")) else "error"
            orchestrator.register_run_end(
                run_id,
                status=status,
                state_update={"mood": str((context or {}).get("mood", "active"))},
            )
            if handoff_id and status == "ok":
                orchestrator.acknowledge_handoff(handoff_id, "main", "spawn accepted")
            if isinstance(wrapped.get("response"), dict):
                return wrapped["response"]
            return wrapped

        # Fallback path: direct gateway spawn to preserve legacy behavior.
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
    content = message.get("content", "")
    try:
        if callable(maybe_apply_model_intent):
            maybe_apply_model_intent(str(content))
    except Exception:
        pass

    # Route message
    route = await handler.route_message(message)
    
    # Get message content
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
