#!/usr/bin/env python3
"""
Message Handler with router-backed Telegram response handling.

Integrates the policy router with OpenClaw gateway for:
- Multi-chat response with OpenAI escalation when needed
- Reply-to-message threading
- Prompt caching
- Context summarization
- Reply provenance capture
"""

import os
import json
import asyncio
from typing import Optional
from agent_orchestration import build_default_orchestrator
from c_lawd_conversation_kernel import (
    build_c_lawd_surface_kernel,
    build_c_lawd_surface_kernel_packet,
)
from policy_router import PolicyRouter, build_chat_payload
from telegram_recall import build_recall_context
from pathlib import Path

try:
    import aiohttp
except Exception:  # pragma: no cover - optional dependency in tests/light runtimes
    aiohttp = None

# Configuration
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:18789")
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")  # Set your token
MAX_QUEUE_DEPTH = int(os.environ.get("MAX_QUEUE_DEPTH", "5"))
MAX_LATENCY_MS = int(os.environ.get("MAX_LATENCY_MS", "30000"))
MAX_HISTORY_MESSAGES = int(os.environ.get("OPENCLAW_TELEGRAM_HISTORY_MESSAGES", "24"))
HISTORY_PATH = Path(
    os.environ.get(
        "OPENCLAW_TELEGRAM_HISTORY_PATH",
        str(Path(__file__).resolve().parents[1] / "state_runtime" / "telegram_message_handler_history.json"),
    )
)
PROVENANCE_PATH = Path(
    os.environ.get(
        "OPENCLAW_TELEGRAM_REPLY_PROVENANCE_PATH",
        str(Path(__file__).resolve().parents[1] / "state_runtime" / "telegram_reply_provenance.jsonl"),
    )
)


class MessageHandler:
    """Handles Telegram messages with router-backed prompt assembly and provenance."""
    
    def __init__(self, gateway_url: str, token: str, *, router: Optional[PolicyRouter] = None, history_path: Path | None = None):
        self.gateway_url = gateway_url
        self.token = token
        self.queue_depth = 0
        self.avg_latency = 0
        self.router = router or PolicyRouter()
        self.history_path = Path(history_path) if history_path else HISTORY_PATH
        self.message_history_by_chat = self._load_histories()

    def append_reply_provenance(self, envelope: dict) -> None:
        PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PROVENANCE_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, ensure_ascii=True) + "\n")

    def _load_histories(self) -> dict[str, list[dict]]:
        if not self.history_path.exists():
            return {}
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        histories: dict[str, list[dict]] = {}
        for chat_id, rows in data.items():
            if not isinstance(rows, list):
                continue
            cleaned = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                role = str(row.get("role", "")).strip()
                content = str(row.get("content", "")).strip()
                if role and content:
                    cleaned.append({"role": role, "content": content})
            if cleaned:
                histories[str(chat_id)] = cleaned[-MAX_HISTORY_MESSAGES:]
        return histories

    def _save_histories(self) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(
            json.dumps(self.message_history_by_chat, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _history_for_chat(self, chat_id: str | None) -> list[dict]:
        if chat_id is None:
            return []
        return list(self.message_history_by_chat.get(str(chat_id), []))

    def _append_history(self, chat_id: str | None, *, role: str, content: str) -> None:
        if chat_id is None:
            return
        key = str(chat_id)
        rows = list(self.message_history_by_chat.get(key, []))
        rows.append({"role": role, "content": content})
        self.message_history_by_chat[key] = rows[-MAX_HISTORY_MESSAGES:]
        self._save_histories()
        
    async def check_load(self) -> dict:
        """Check current system load."""
        if aiohttp is None:
            return {"overloaded": False, "queue_depth": 0, "latency": 0}
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
        content = str(message.get("content", ""))
        payload = build_chat_payload(content, temperature=0.0, max_tokens=512)
        context = {
            "input_text": content,
            "surface": "telegram",
            "channel": "telegram",
            "chat_id": str(message.get("chat_id", "")),
        }
        route = self.router.explain_route("conversation", context_metadata=context, payload=payload)
        chosen = route.get("chosen") or {}

        return {
            "route": chosen.get("provider") or "unavailable",
            "reason": route.get("reason") or "default conversation routing",
            "message_id": message.get("message_id"),
            "chat_id": message.get("chat_id"),
            "surface": route.get("surface") or "telegram",
            "policy_profile": route.get("policy_profile") or "default",
            "selected_provider": chosen.get("provider"),
            "selected_model": chosen.get("model"),
            "route_explain": route,
            "load": load,
        }
    
    def _auth_headers(self) -> dict:
        """Get authorization headers."""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}
    
    def cache_prompt(self, prompt: str, *, context: str = "", surface: str = "telegram") -> str:
        """Build a stable, surface-specific prompt prefix for better caching and routing."""
        static_context = build_c_lawd_surface_kernel(
            surface=surface,
            include_memory=True,
            mode="conversation",
        )
        if context:
            return f"{static_context}\n\n## Recent chat context\n\n{context}\n\n## User message\n\n{prompt}"
        return f"{static_context}\n\n## User message\n\n{prompt}"
    
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
        raise RuntimeError("aiohttp is required to send Telegram replies")
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
    """Spawn an OpenAI subagent to handle a message.
    
    Uses OpenClaw's sessions_spawn internally.
    """
    if aiohttp is None:
        raise RuntimeError("aiohttp is required to spawn gateway subagents")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    orchestrator = build_default_orchestrator()
    spawn_plan = orchestrator.prepare_spawn(
        task=task,
        context=context or {},
        priority=(context or {}).get("priority", "normal"),
        specialization_tags=(context or {}).get("specialization_tags"),
        providers=["openai-codex/gpt-5.4"],
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
    """Process an incoming Telegram message through the router-backed path."""
    
    # Route message
    route = await handler.route_message(message)
    
    # Get message content
    content = message.get("content", "")
    message_id = message.get("message_id")
    chat_id = message.get("chat_id")
    session_start = bool(message.get("session_start", False))

    # Optional semantic recall hook from Telegram vector store (disabled by default).
    recall_context = build_recall_context(
        str(content),
        env=os.environ,
        session_start=session_start,
        chat_id=str(chat_id) if chat_id is not None else None,
    )
    content_with_recall = (
        f"{recall_context['block']}\n\n{content}"
        if recall_context.get("block")
        else str(content)
    )
    
    # Get conversation context
    history = handler._history_for_chat(str(chat_id) if chat_id is not None else None)[-10:]
    context = handler.summarize_context(history)
    kernel_packet = build_c_lawd_surface_kernel_packet(
        surface="telegram",
        include_memory=True,
        mode="conversation",
    )
    full_prompt = handler.cache_prompt(content_with_recall, context=context, surface="telegram")

    payload = build_chat_payload(full_prompt, temperature=0.0, max_tokens=800)
    runtime_context = {
        "input_text": content_with_recall,
        "surface": "telegram",
        "channel": "telegram",
        "chat_id": str(chat_id) if chat_id is not None else "",
        "message_id": str(message_id) if message_id is not None else "",
        "queue_depth": route.get("load", {}).get("queue_depth", 0),
        "overloaded": route.get("load", {}).get("overloaded", False),
        "kernel_id": kernel_packet.kernel_id,
        "kernel_hash": kernel_packet.kernel_hash,
        "surface_overlay": kernel_packet.surface_overlay,
    }
    result = handler.router.execute_with_escalation("conversation", payload, context_metadata=runtime_context)
    if result.get("ok"):
        reply_text = str(result.get("text") or "").strip() or "I completed the routing path but received an empty reply."
    else:
        reason = str(result.get("reason_code") or "router_error")
        reply_text = f"I couldn't complete the Telegram routing path cleanly. Blocker: {reason}."
    
    send_result = None

    # Send reply with threading (replyTo)
    if chat_id and message_id:
        send_result = await send_telegram_reply(
            chat_id=str(chat_id),
            message_id=str(message_id),
            text=reply_text,
            gateway_url=GATEWAY_URL,
            token=GATEWAY_TOKEN
        )
    
    # Update history
    handler._append_history(str(chat_id) if chat_id is not None else None, role="user", content=content)
    handler._append_history(str(chat_id) if chat_id is not None else None, role="assistant", content=reply_text)

    route_provenance = dict(result.get("route_provenance") or {})
    route_provenance.setdefault("surface", route.get("surface") or "telegram")
    route_provenance.setdefault("policy_profile", route.get("policy_profile") or "default")
    route_provenance.setdefault("selected_provider", route.get("selected_provider"))
    route_provenance.setdefault("selected_model", route.get("selected_model"))
    route_provenance.setdefault("reason_code", result.get("reason_code") or "router_error")
    route_provenance.setdefault("kernel_id", kernel_packet.kernel_id)
    route_provenance.setdefault("kernel_hash", kernel_packet.kernel_hash)
    route_provenance.setdefault("surface_overlay", kernel_packet.surface_overlay)
    route_provenance.setdefault("memory_blocks", list(recall_context.get("memory_blocks") or []))
    route_provenance.setdefault("files_touched", list(recall_context.get("files_touched") or []))
    route_provenance.setdefault("tests_run", [])
    route_provenance.setdefault("uncertainties", list(recall_context.get("uncertainties") or []))

    reply_id = None
    if isinstance(send_result, dict):
        reply_id = (
            send_result.get("message_id")
            or send_result.get("id")
            or (send_result.get("result") or {}).get("message_id")
            or (send_result.get("kwargs") or {}).get("message_id")
        )

    provenance_envelope = {
        "reply_id": str(reply_id or message_id or ""),
        "surface": "telegram",
        "policy_profile": route_provenance.get("policy_profile"),
        "reason_code": route_provenance.get("reason_code"),
        "provider": route_provenance.get("selected_provider") or result.get("provider"),
        "model": route_provenance.get("selected_model") or result.get("model"),
        "memory_blocks": list(route_provenance.get("memory_blocks") or []),
        "files_touched": list(route_provenance.get("files_touched") or []),
        "tests_run": list(route_provenance.get("tests_run") or []),
        "uncertainties": list(route_provenance.get("uncertainties") or []),
        "operator_visible_summary": (
            "route="
            f"{route_provenance.get('selected_provider') or result.get('provider') or 'unknown'}"
            "/"
            f"{route_provenance.get('selected_model') or result.get('model') or 'unknown'} "
            f"memory={len(route_provenance.get('memory_blocks') or [])} "
            f"files={len(route_provenance.get('files_touched') or [])} "
            f"tests={len(route_provenance.get('tests_run') or [])} "
            f"uncertainties={len(route_provenance.get('uncertainties') or [])}"
        ),
        "chat_id": str(chat_id) if chat_id is not None else "",
        "message_id": str(message_id) if message_id is not None else "",
        "kernel_id": route_provenance.get("kernel_id"),
        "kernel_hash": route_provenance.get("kernel_hash"),
        "surface_overlay": route_provenance.get("surface_overlay"),
    }
    handler.append_reply_provenance(provenance_envelope)

    return {
        "success": True,
        "route": route["route"],
        "reason": route["reason"],
        "provider": result.get("provider"),
        "model": result.get("model"),
        "route_provenance": route_provenance,
        "reply_provenance": provenance_envelope,
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
