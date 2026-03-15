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
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import aiohttp
except Exception:  # pragma: no cover
    aiohttp = None

# CEL tool imports are optional to preserve backward compatibility.
REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
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
from agent_orchestration import build_default_orchestrator
from telegram_recall import build_recall_block
try:
    from model_intent_router import route_metadata_for_text
except Exception:  # pragma: no cover
    route_metadata_for_text = None

from api.discord_bot_support import (  # type: ignore
    build_telegram_chat_prompt,
    extract_agent_reply_text,
    extract_last_json_object,
    source_context_packet_text,
    telegram_memory_context_text,
    user_context_packet_text,
)
from api.telegram_memory import ingest_telegram_exchange  # type: ignore
from policy_router import PolicyRouter, build_chat_payload  # type: ignore

# Configuration
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:18789")
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")  # Set your token
MAX_QUEUE_DEPTH = int(os.environ.get("MAX_QUEUE_DEPTH", "5"))
MAX_LATENCY_MS = int(os.environ.get("MAX_LATENCY_MS", "30000"))
OPENCLAW_BIN = os.environ.get(
    "OPENCLAW_CLI_BIN",
    str(REPO_ROOT / ".runtime" / "openclaw" / "openclaw.mjs"),
).strip()
TELEGRAM_AGENT_ID = os.environ.get("OPENCLAW_TELEGRAM_AGENT_ID", "telegram-dali").strip() or "telegram-dali"
TELEGRAM_EXEC_AGENT_ID = os.environ.get("OPENCLAW_TELEGRAM_EXEC_AGENT_ID", "main").strip() or "main"
TELEGRAM_DEFAULT_PROVIDER = os.environ.get("OPENCLAW_TELEGRAM_DEFAULT_PROVIDER", "openai_auth").strip() or "openai_auth"
TELEGRAM_OAUTH_MODEL = os.environ.get("OPENCLAW_TELEGRAM_OAUTH_MODEL", "openai/gpt-5.4-pro").strip() or "openai/gpt-5.4-pro"
TELEGRAM_AUTH_THINKING = os.environ.get("OPENCLAW_TELEGRAM_AUTH_THINKING", "medium").strip() or "medium"
TELEGRAM_AUTH_TIMEOUT_SECONDS = max(
    30,
    int(os.environ.get("OPENCLAW_TELEGRAM_AUTH_TIMEOUT_SECONDS", "180") or "180"),
)
TELEGRAM_MAX_TOKENS = max(256, int(os.environ.get("OPENCLAW_TELEGRAM_MAX_TOKENS", "1200") or "1200"))
TELEGRAM_TEMPERATURE = float(os.environ.get("OPENCLAW_TELEGRAM_TEMPERATURE", "0.2") or "0.2")


def _payload_prompt_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    if isinstance(messages, list):
        parts: list[str] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                parts.append(content.strip())
        if parts:
            return "\n\n".join(parts)
    for key in ("prompt", "input", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _auth_reason_code_from_detail(detail: str) -> str:
    text = str(detail or "").lower()
    if "429" in text or "rate limit" in text or "quota" in text:
        return "request_http_429"
    if "timeout" in text or "timed out" in text:
        return "request_timeout"
    if "auth" in text or "login" in text or "no available auth profile" in text or "configure auth" in text:
        return "auth_login_required"
    return "auth_cli_failed"


def _run_openclaw_auth_prompt(
    payload: dict[str, Any],
    model_id: str | None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = _payload_prompt_text(payload or {})
    if not prompt:
        return {"ok": False, "reason_code": "empty_prompt"}
    runtime_context = dict(context or {})
    selected_model = str(model_id or runtime_context.get("override_model") or TELEGRAM_OAUTH_MODEL).strip()
    exec_agent_id = str(runtime_context.get("exec_agent_id") or TELEGRAM_EXEC_AGENT_ID).strip() or TELEGRAM_EXEC_AGENT_ID
    cmd = [
        "node",
        OPENCLAW_BIN,
        "agent",
        "--local",
        "--agent",
        exec_agent_id,
        "--json",
        "--message",
        prompt,
        "--model",
        selected_model,
        "--thinking",
        TELEGRAM_AUTH_THINKING,
        "--timeout",
        str(TELEGRAM_AUTH_TIMEOUT_SECONDS),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=TELEGRAM_AUTH_TIMEOUT_SECONDS + 30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        detail = str(exc)
        return {"ok": False, "reason_code": _auth_reason_code_from_detail(detail), "error": detail}
    except Exception as exc:
        detail = str(exc)
        return {"ok": False, "reason_code": "auth_cli_failed", "error": detail}

    stdout_text = proc.stdout or ""
    stderr_text = (proc.stderr or "").strip()
    if proc.returncode != 0:
        detail = stderr_text or stdout_text.strip() or f"exit {proc.returncode}"
        return {"ok": False, "reason_code": _auth_reason_code_from_detail(detail), "error": detail}

    try:
        response_payload = extract_last_json_object(stdout_text)
    except Exception as exc:
        detail = stderr_text or str(exc) or stdout_text.strip()
        return {"ok": False, "reason_code": "auth_cli_parse_error", "error": detail}

    reply_text = extract_agent_reply_text(response_payload).strip()
    if not reply_text:
        return {"ok": False, "reason_code": "response_null", "error": "No response text returned."}
    return {"ok": True, "text": reply_text}


class MessageHandler:
    """Handles messages with load balancing and efficiency optimizations."""
    
    def __init__(self, gateway_url: str, token: str, router: PolicyRouter | None = None):
        self.gateway_url = gateway_url
        self.token = token
        self.router = router or PolicyRouter(handlers={"openai_auth": _run_openclaw_auth_prompt})
        self.queue_depth = 0
        self.avg_latency = 0
        self.message_history = []  # For context summarization
        
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


def _message_text(message: dict[str, Any]) -> str:
    return str(message.get("content", "") or "").strip()


def _message_author_name(message: dict[str, Any]) -> str:
    for key in ("author_name", "sender_name", "from_name", "author"):
        value = str(message.get(key, "") or "").strip()
        if value:
            return value
    return "unknown"


def _message_chat_title(message: dict[str, Any]) -> str:
    for key in ("chat_title", "chat_name", "chat_label"):
        value = str(message.get(key, "") or "").strip()
        if value:
            return value
    return "telegram"


def _message_thread_id(message: dict[str, Any]) -> str:
    for key in ("reply_to_message_id", "thread_message_id", "replyTo"):
        value = str(message.get(key, "") or "").strip()
        if value:
            return value
    meta = message.get("meta")
    if isinstance(meta, dict):
        for key in ("reply_to_message_id", "thread_message_id"):
            value = str(meta.get(key, "") or "").strip()
            if value:
                return value
    return ""


def _route_metadata(message_text: str) -> dict[str, Any]:
    if not callable(route_metadata_for_text):
        return {}
    try:
        payload = route_metadata_for_text(message_text)
    except Exception:
        return {}
    return dict(payload or {})


def _build_telegram_runtime_request(message: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    content = _message_text(message)
    message_id = str(message.get("message_id") or "").strip()
    chat_id = str(message.get("chat_id") or "").strip()
    chat_title = _message_chat_title(message)
    author_name = _message_author_name(message)
    thread_message_id = _message_thread_id(message)
    session_start = bool(message.get("session_start", False))

    memory_context = telegram_memory_context_text(
        chat_id=chat_id,
        author_name=author_name,
        exclude_message_id=message_id or None,
        thread_message_id=thread_message_id or None,
        limit=6,
    )
    thread_context = [line for line in memory_context if "reply-to" in line][:3]
    user_context = user_context_packet_text(
        limit=4,
        context=f"telegram\n{content}",
        agent_id=TELEGRAM_AGENT_ID,
        channel_name="telegram",
    )
    source_context = source_context_packet_text(limit=6)
    recall_block = build_recall_block(
        content,
        env=os.environ,
        session_start=session_start,
    )
    prompt = build_telegram_chat_prompt(
        agent_id=TELEGRAM_AGENT_ID,
        author_name=author_name,
        chat_title=chat_title,
        content=content,
        memory_context=memory_context,
        thread_context=thread_context,
        user_context=user_context,
        source_context=source_context,
        recall_context=recall_block,
    )

    route_meta = _route_metadata(content)
    if not route_meta.get("preferred_provider"):
        route_meta["preferred_provider"] = TELEGRAM_DEFAULT_PROVIDER
    if route_meta.get("preferred_provider") == "openai_auth" and not route_meta.get("override_model"):
        route_meta["override_model"] = TELEGRAM_OAUTH_MODEL
    context_metadata: dict[str, Any] = {
        "input_text": content,
        "surface": "telegram",
        "agent_id": TELEGRAM_AGENT_ID,
        "exec_agent_id": TELEGRAM_EXEC_AGENT_ID,
        "author_name": author_name,
        "chat_id": chat_id,
        "chat_title": chat_title,
        "thread_message_id": thread_message_id or None,
        "session_start": session_start,
    }
    context_metadata.update({k: v for k, v in route_meta.items() if v})
    return prompt, context_metadata


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
        if aiohttp is None:
            raise RuntimeError("aiohttp is required for direct gateway spawn")
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
    """Process an incoming Telegram message through the shared router/context stack."""
    content = _message_text(message)
    if not content:
        return {"success": False, "reason": "empty_content"}

    message_id = str(message.get("message_id") or "").strip()
    chat_id = str(message.get("chat_id") or "").strip()
    prompt, context_metadata = _build_telegram_runtime_request(message)
    payload = build_chat_payload(
        prompt,
        temperature=TELEGRAM_TEMPERATURE,
        max_tokens=TELEGRAM_MAX_TOKENS,
    )
    result = handler.router.execute_with_escalation(
        "conversation",
        payload,
        context_metadata=context_metadata,
    )

    if result.get("ok"):
        reply_text = str(result.get("text") or "").strip()
    elif result.get("deferred"):
        reply_text = "Local inference is paused while fishtank mode is active. Switch back to work mode to resume Telegram replies."
    else:
        reason = str(result.get("reason_code") or "provider_error").strip()
        reply_text = f"I couldn't complete that request cleanly just now ({reason})."

    send_result: dict[str, Any] = {}
    if chat_id and message_id:
        send_result = await send_telegram_reply(
            chat_id=chat_id,
            message_id=message_id,
            text=reply_text,
            gateway_url=handler.gateway_url,
            token=handler.token,
        )
        synthetic_reply_id = (
            str(send_result.get("message_id") or "").strip()
            or str(send_result.get("messageId") or "").strip()
            or f"assistant-reply-{message_id}"
        )
        try:
            ingest_telegram_exchange(
                chat_id=chat_id,
                chat_title=_message_chat_title(message),
                message_id=synthetic_reply_id,
                author_id=TELEGRAM_AGENT_ID,
                author_name="Dali",
                role="assistant",
                content=reply_text,
                created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                agent_scope="main",
                source="telegram_gateway_reply",
                meta={
                    "reply_to_message_id": message_id,
                    "router_provider": result.get("provider"),
                    "router_model": result.get("model"),
                    "reason_code": result.get("reason_code"),
                    "synthetic_message_id": synthetic_reply_id.startswith("assistant-reply-"),
                },
            )
        except Exception:
            pass

    handler.message_history.append({"role": "user", "content": content})
    handler.message_history.append({"role": "assistant", "content": reply_text})

    return {
        "success": True,
        "route": result.get("provider") or "unavailable",
        "model": result.get("model"),
        "reason": result.get("reason_code") or "success",
        "request_id": result.get("request_id"),
        "message_sent": bool(send_result) if chat_id and message_id else False,
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
