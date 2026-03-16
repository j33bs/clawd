#!/usr/bin/env python3
"""Discord bot for OpenClaw project/status commands."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
SCRIPTS_ROOT = REPO_ROOT / "workspace" / "scripts"
for path in (SOURCE_UI_ROOT, SCRIPTS_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

ENV_FILE = Path.home() / ".config" / "openclaw" / "discord-bot.env"


def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()

try:
    import discord
    from discord import app_commands
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"discord.py is required: {exc}")

from api.discord_bot_support import (  # type: ignore
    ALLOWED_PRIORITIES,
    ALLOWED_TASK_STATUSES,
    build_discord_chat_prompt,
    discord_memory_context_text,
    extract_agent_reply_text,
    extract_last_json_object,
    ops_health_text,
    parse_channel_agent_map,
    project_status_text,
    sim_status_text,
    task_create_text,
    task_move_text,
    user_context_packet_text,
)
from api.discord_memory import ingest_discord_exchange  # type: ignore
from vllm_deferred_queue import (  # type: ignore
    enqueue_discord_message,
    list_entries as list_deferred_entries,
    should_defer_local_vllm,
    update_entry as update_deferred_entry,
)

TOKEN = os.environ.get("OPENCLAW_DISCORD_BOT_TOKEN", "").strip()
APP_ID = os.environ.get("OPENCLAW_DISCORD_APP_ID", "").strip()
GUILD_ID = os.environ.get("OPENCLAW_DISCORD_GUILD_ID", "").strip()
STATUS_TEXT = os.environ.get("OPENCLAW_DISCORD_BOT_STATUS", "watching Dali").strip() or "watching Dali"
ALLOWED_CHANNEL_IDS = {
    int(value)
    for value in os.environ.get("OPENCLAW_DISCORD_ALLOWED_CHANNEL_IDS", "").split(",")
    if value.strip().isdigit()
}
MUTATION_ROLE_IDS = {
    int(value)
    for value in os.environ.get("OPENCLAW_DISCORD_MUTATION_ROLE_IDS", "").split(",")
    if value.strip().isdigit()
}
CHAT_CHANNEL_AGENT_MAP = parse_channel_agent_map(os.environ.get("OPENCLAW_DISCORD_CHAT_CHANNEL_AGENT_MAP", ""))
OPEN_FORUM_CHANNEL_IDS = {
    int(value)
    for value in os.environ.get("OPENCLAW_DISCORD_OPEN_FORUM_CHANNEL_IDS", "1480814946479636574").split(",")
    if value.strip().isdigit()
}
OPEN_FORUM_MAX_AUTONOMOUS_TURNS = max(0, int(os.environ.get("OPENCLAW_DISCORD_OPEN_FORUM_MAX_AUTONOMOUS_TURNS", "3") or "3"))
AGENT_DISPLAY_NAMES: dict[str, str] = {
    "discord-orchestrator": "Dali 🎨",
    "discord-clawd": "c_lawd 🜃",
    "discord-gpt54": "ChatGPT",
    "discord-codex53": "Lumen",
    "discord-minimax25": "Dali (research)",
}
CHAT_TIMEOUT_SECONDS = max(15, int(os.environ.get("OPENCLAW_DISCORD_CHAT_TIMEOUT_SECONDS", "180") or "180"))
CHAT_THINKING_LEVEL = (os.environ.get("OPENCLAW_DISCORD_CHAT_THINKING", "low").strip().lower() or "low")
MEMORY_CHANNEL_IDS = {
    int(value)
    for value in os.environ.get("OPENCLAW_DISCORD_MEMORY_CHANNEL_IDS", "").split(",")
    if value.strip().isdigit()
}
RESEARCH_CHANNEL_IDS = {
    int(value)
    for value in os.environ.get("OPENCLAW_DISCORD_RESEARCH_CHANNEL_IDS", "").split(",")
    if value.strip().isdigit()
}
MEMORY_AGENT_SCOPE = os.environ.get("OPENCLAW_DISCORD_MEMORY_AGENT_SCOPE", "main").strip() or "main"
OPENCLAW_BIN = os.environ.get(
    "OPENCLAW_CLI_BIN",
    str(REPO_ROOT / ".runtime" / "openclaw" / "openclaw.mjs"),
).strip()
DEFERRED_RESUME_INTERVAL_SECONDS = max(
    10,
    int(os.environ.get("OPENCLAW_DISCORD_DEFERRED_RESUME_INTERVAL_SECONDS", "30") or "30"),
)
DEFERRED_MESSAGE_TTL_SECONDS = max(
    300,
    int(os.environ.get("OPENCLAW_DISCORD_DEFERRED_MESSAGE_TTL_SECONDS", "1800") or "1800"),
)

if not TOKEN:
    raise SystemExit("Missing OPENCLAW_DISCORD_BOT_TOKEN in ~/.config/openclaw/discord-bot.env")


def _has_any_role(member: discord.abc.User | discord.Member | None, role_ids: Iterable[int]) -> bool:
    if not isinstance(member, discord.Member):
        return False
    member_role_ids = {role.id for role in member.roles}
    return any(role_id in member_role_ids for role_id in role_ids)


def _memory_enabled_for_channel(channel_id: int | None) -> bool:
    if channel_id is None:
        return False
    if MEMORY_CHANNEL_IDS:
        return int(channel_id) in MEMORY_CHANNEL_IDS
    return int(channel_id) in CHAT_CHANNEL_AGENT_MAP


def _research_enabled_for_channel(channel_id: int | None) -> bool:
    if channel_id is None:
        return False
    return int(channel_id) in RESEARCH_CHANNEL_IDS


async def _ensure_allowed_channel(interaction: discord.Interaction) -> bool:
    if not ALLOWED_CHANNEL_IDS:
        return True
    channel_id = getattr(interaction.channel, "id", None)
    if channel_id in ALLOWED_CHANNEL_IDS:
        return True
    message = "This command is not allowed in this channel."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)
    return False


async def _ensure_mutation_access(interaction: discord.Interaction) -> bool:
    if not await _ensure_allowed_channel(interaction):
        return False
    member = interaction.user
    perms = getattr(member, "guild_permissions", None)
    if perms and (perms.administrator or perms.manage_guild):
        return True
    if MUTATION_ROLE_IDS and _has_any_role(member, MUTATION_ROLE_IDS):
        return True
    message = "You do not have permission to modify tasks."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)
    return False


class OpenClawDiscordBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents, application_id=int(APP_ID) if APP_ID else None)
        self.tree = app_commands.CommandTree(self)
        self.guild_object = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None
        self._channel_locks: dict[int, asyncio.Lock] = {}
        self._deferred_resume_task: asyncio.Task | None = None
        self._register_commands()

    async def setup_hook(self) -> None:
        if self.guild_object is not None:
            self.tree.copy_global_to(guild=self.guild_object)
            synced = await self.tree.sync(guild=self.guild_object)
            print(f"Synced {len(synced)} guild commands to {self.guild_object.id}")
        else:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} global commands")

    async def on_ready(self) -> None:
        await self.change_presence(activity=discord.Game(name=STATUS_TEXT))
        if self._deferred_resume_task is None or self._deferred_resume_task.done():
            self._deferred_resume_task = asyncio.create_task(self._resume_deferred_messages_loop())
        print(f"Discord bot ready as {self.user} ({self.user.id if self.user else 'unknown'})")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        channel_id = getattr(message.channel, "id", None)
        if channel_id not in CHAT_CHANNEL_AGENT_MAP:
            return
        content = (message.content or "").strip()
        attachment_urls = [attachment.url for attachment in message.attachments[:5] if attachment.url]
        if not content and not attachment_urls:
            return
        # Support multi-agent channels: agent value may be "agent1+agent2"
        agent_ids = [a.strip() for a in CHAT_CHANNEL_AGENT_MAP[channel_id].split("+") if a.strip()]
        if _memory_enabled_for_channel(channel_id):
            try:
                ingest_discord_exchange(
                    guild_id=getattr(message.guild, "id", None),
                    guild_name=getattr(message.guild, "name", "") or "",
                    channel_id=channel_id,
                    channel_name=getattr(message.channel, "name", "") or "",
                    message_id=str(message.id),
                    author_id=getattr(message.author, "id", None),
                    author_name=message.author.display_name,
                    role="user",
                    content=message.content or "",
                    attachments=attachment_urls,
                    created_at=message.created_at.isoformat() if getattr(message, "created_at", None) else "",
                    agent_scope=MEMORY_AGENT_SCOPE,
                    ingest_research=_research_enabled_for_channel(channel_id),
                )
            except Exception as exc:
                print(f"discord memory ingest failed for user message: {exc}")
        if should_defer_local_vllm():
            entry = enqueue_discord_message(
                guild_id=getattr(message.guild, "id", None),
                channel_id=int(channel_id),
                message_id=int(message.id),
                author_name=message.author.display_name,
                agent_ids=agent_ids,
                attachments=attachment_urls,
                open_forum=(len(agent_ids) > 1 and channel_id in OPEN_FORUM_CHANNEL_IDS),
            )
            await message.reply(
                f"Queued while fishtank mode is active. I will resume this when work mode returns. (`{entry['id']}`)",
                mention_author=False,
            )
            return
        lock = self._channel_locks.setdefault(channel_id, asyncio.Lock())
        async with lock:
            try:
                replies = await self._generate_replies(
                    message=message,
                    agent_ids=agent_ids,
                    attachment_urls=attachment_urls,
                )
            except asyncio.TimeoutError:
                await message.reply("[multi-agent] Timed out waiting for the model." if len(agent_ids) > 1 else f"[{agent_ids[0]}] Timed out waiting for the model.", mention_author=False)
                return
            except Exception as exc:
                await message.reply(f"[multi-agent] Model call failed: {exc}" if len(agent_ids) > 1 else f"[{agent_ids[0]}] Model call failed: {exc}", mention_author=False)
                return
        await self._deliver_replies(message=message, channel_id=int(channel_id), replies=replies)

    async def close(self) -> None:
        if self._deferred_resume_task is not None:
            self._deferred_resume_task.cancel()
        await super().close()

    async def _generate_replies(
        self,
        *,
        message: discord.Message,
        agent_ids: list[str],
        attachment_urls: list[str],
    ) -> list[tuple[str, str]]:
        async with message.channel.typing():
            channel_id = int(getattr(message.channel, "id", 0) or 0)
            if len(agent_ids) > 1 and channel_id in OPEN_FORUM_CHANNEL_IDS:
                return await self._run_multi_agent_open_forum(
                    agent_ids=agent_ids,
                    message=message,
                    attachments=attachment_urls,
                )
            if len(agent_ids) > 1:
                reply_text, reply_agent_id = await self._run_multi_agent_consensus(
                    agent_ids=agent_ids,
                    message=message,
                    attachments=attachment_urls,
                )
                return [(reply_agent_id, self._format_multi_agent_public_reply(agent_ids, reply_text))]
            reply_agent_id = agent_ids[0]
            public_reply_text = await self._run_chat_agent(
                agent_id=reply_agent_id,
                message=message,
                attachments=attachment_urls,
            )
            return [(reply_agent_id, public_reply_text)]

    async def _deliver_replies(
        self,
        *,
        message: discord.Message,
        channel_id: int,
        replies: list[tuple[str, str]],
    ) -> None:
        for reply_index, (reply_agent_id, public_reply_text) in enumerate(replies, start=1):
            if _memory_enabled_for_channel(channel_id):
                try:
                    ingest_discord_exchange(
                        guild_id=getattr(message.guild, "id", None),
                        guild_name=getattr(message.guild, "name", "") or "",
                        channel_id=channel_id,
                        channel_name=getattr(message.channel, "name", "") or "",
                        message_id=f"{message.id}:assistant:{reply_agent_id}:{reply_index}",
                        author_id=getattr(self.user, "id", None),
                        author_name=getattr(self.user, "display_name", None) or getattr(self.user, "name", "Dali"),
                        role="assistant",
                        content=public_reply_text,
                        attachments=[],
                        created_at="",
                        agent_scope=MEMORY_AGENT_SCOPE,
                        agent_id=reply_agent_id,
                        ingest_research=_research_enabled_for_channel(channel_id),
                    )
                except Exception as exc:
                    print(f"discord memory ingest failed for assistant reply ({reply_agent_id}): {exc}")
            chunks = self._chunk_reply(public_reply_text)
            for chunk in chunks:
                await message.reply(chunk, mention_author=False)

    async def _resume_deferred_messages_loop(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            if should_defer_local_vllm():
                await asyncio.sleep(DEFERRED_RESUME_INTERVAL_SECONDS)
                continue
            pending = list_deferred_entries(kind="discord_message", status="deferred", limit=4)
            if not pending:
                await asyncio.sleep(DEFERRED_RESUME_INTERVAL_SECONDS)
                continue
            for entry in pending:
                try:
                    await self._resume_deferred_message(entry)
                except asyncio.CancelledError:  # pragma: no cover
                    raise
                except Exception as exc:
                    update_deferred_entry(
                        str(entry.get("id") or ""),
                        status="failed",
                        error=_truncate_single_line(str(exc), limit=220),
                    )
            await asyncio.sleep(5)

    async def _resume_deferred_message(self, entry: dict[str, object]) -> None:
        entry_id = str(entry.get("id") or "")
        created_at = self._parse_iso(str(entry.get("created_at") or ""))
        if created_at is not None:
            age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
            if age_seconds > DEFERRED_MESSAGE_TTL_SECONDS:
                update_deferred_entry(
                    entry_id,
                    status="review_required",
                    review_reason="stale_conversation",
                )
                return

        channel_id = int(entry.get("channel_id", 0) or 0)
        message_id = int(entry.get("message_id", 0) or 0)
        agent_ids = [str(item) for item in list(entry.get("agent_ids") or []) if str(item).strip()]
        if channel_id <= 0 or message_id <= 0 or not agent_ids:
            update_deferred_entry(entry_id, status="failed", error="invalid_deferred_discord_entry")
            return

        channel = self.get_channel(channel_id)
        if channel is None:
            channel = await self.fetch_channel(channel_id)
        if channel is None or not hasattr(channel, "fetch_message"):
            update_deferred_entry(entry_id, status="failed", error="discord_channel_unavailable")
            return
        message = await channel.fetch_message(message_id)
        if message is None:
            update_deferred_entry(entry_id, status="failed", error="discord_message_missing")
            return

        update_deferred_entry(
            entry_id,
            status="processing",
            attempts=int(entry.get("attempts", 0) or 0) + 1,
        )
        lock = self._channel_locks.setdefault(channel_id, asyncio.Lock())
        attachment_urls = [str(item) for item in list(entry.get("attachments") or []) if str(item).strip()]
        async with lock:
            replies = await self._generate_replies(
                message=message,
                agent_ids=agent_ids,
                attachment_urls=attachment_urls,
            )
        await self._deliver_replies(message=message, channel_id=channel_id, replies=replies)
        update_deferred_entry(
            entry_id,
            status="completed",
            completed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            reply_count=len(replies),
        )

    @staticmethod
    def _parse_iso(value: str) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None

    async def _run_chat_agent(
        self,
        *,
        agent_id: str,
        message: discord.Message,
        attachments: list[str],
        prior_drafts: list[dict[str, str]] | None = None,
        coordination_instruction: str | None = None,
    ) -> str:
        memory_context = []
        if _memory_enabled_for_channel(getattr(message.channel, "id", None)):
            memory_context = discord_memory_context_text(
                channel_id=int(getattr(message.channel, "id", 0) or 0),
                author_name=message.author.display_name,
                exclude_message_id=int(message.id),
                limit=4,
            )
        user_context = user_context_packet_text(
            limit=4,
            context=f"{getattr(message.channel, 'name', '') or ''}\n{message.content or ''}",
            agent_id=agent_id,
            channel_name=getattr(message.channel, "name", "") or "",
        )
        prompt = build_discord_chat_prompt(
            agent_id=agent_id,
            author_name=message.author.display_name,
            channel_name=getattr(message.channel, "name", "") or "",
            content=message.content or "",
            attachments=attachments,
            memory_context=memory_context,
            user_context=user_context,
        )
        if prior_drafts:
            prompt = (
                f"{prompt}\n\n"
                "Private draft context from other beings in this turn:\n"
                f"{self._format_private_drafts(prior_drafts)}\n\n"
                f"{coordination_instruction or 'Use these drafts to coordinate. Add what is missing, correct what is wrong, and move toward one coherent public answer.'}"
            )
        return await self._run_agent_prompt(agent_id=agent_id, prompt=prompt)

    async def _run_agent_prompt(self, *, agent_id: str, prompt: str) -> str:
        cmd = [
            "node",
            OPENCLAW_BIN,
            "agent",
            "--local",
            "--agent",
            agent_id,
            "--json",
            "--message",
            prompt,
            "--thinking",
            CHAT_THINKING_LEVEL,
            "--timeout",
            str(CHAT_TIMEOUT_SECONDS),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(REPO_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_raw, stderr_raw = await asyncio.wait_for(proc.communicate(), timeout=CHAT_TIMEOUT_SECONDS + 30)
        stdout_text = stdout_raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            detail = stderr_text or stdout_text.strip() or f"exit {proc.returncode}"
            raise RuntimeError(_truncate_single_line(detail))
        payload = extract_last_json_object(stdout_text)
        return extract_agent_reply_text(payload)

    async def _run_multi_agent_consensus(
        self,
        *,
        agent_ids: list[str],
        message: discord.Message,
        attachments: list[str],
    ) -> tuple[str, str]:
        drafts: list[dict[str, str]] = []
        draft_failures: list[dict[str, str]] = []
        for agent_id in agent_ids:
            try:
                draft_text = await self._run_chat_agent(
                    agent_id=agent_id,
                    message=message,
                    attachments=attachments,
                    prior_drafts=drafts,
                )
            except Exception as exc:
                draft_failures.append(
                    {
                        "agent_id": agent_id,
                        "display_name": AGENT_DISPLAY_NAMES.get(agent_id, agent_id),
                        "error": _truncate_single_line(str(exc), limit=180),
                    }
                )
                continue
            drafts.append(
                {
                    "agent_id": agent_id,
                    "display_name": AGENT_DISPLAY_NAMES.get(agent_id, agent_id),
                    "reply_text": draft_text,
                }
            )

        if not drafts:
            failure_text = "; ".join(
                f"{item['display_name']}: {item['error']}"
                for item in draft_failures
            ) or "no agent reply returned"
            raise RuntimeError(failure_text)

        if len(drafts) == 1 and not draft_failures:
            return drafts[0]["reply_text"], drafts[0]["agent_id"]

        consensus_agent_id = self._consensus_agent_id(agent_ids, drafts)
        consensus_prompt = self._build_consensus_prompt(
            consensus_agent_id=consensus_agent_id,
            message=message,
            attachments=attachments,
            drafts=drafts,
            draft_failures=draft_failures,
        )
        try:
            consensus_text = await self._run_agent_prompt(
                agent_id=consensus_agent_id,
                prompt=consensus_prompt,
            )
        except Exception as exc:
            consensus_text = self._fallback_consensus_text(
                drafts=drafts,
                draft_failures=draft_failures,
                synthesis_error=_truncate_single_line(str(exc), limit=180),
            )
        return consensus_text, consensus_agent_id

    async def _run_multi_agent_open_forum(
        self,
        *,
        agent_ids: list[str],
        message: discord.Message,
        attachments: list[str],
    ) -> list[tuple[str, str]]:
        drafts: list[dict[str, str]] = []
        replies: list[tuple[str, str]] = []
        failures: list[str] = []
        for agent_id in agent_ids:
            try:
                draft_text = await self._run_chat_agent(
                    agent_id=agent_id,
                    message=message,
                    attachments=attachments,
                    prior_drafts=drafts,
                    coordination_instruction=(
                        "Use these drafts to participate in the same public conversation. "
                        "Add a distinct contribution, respond to concrete issues another being surfaced when useful, "
                        "and keep the message conversational rather than converging to one merged answer."
                    ),
                )
            except Exception as exc:
                failures.append(f"{AGENT_DISPLAY_NAMES.get(agent_id, agent_id)} unavailable: {_truncate_single_line(str(exc), limit=180)}")
                continue
            drafts.append(
                {
                    "agent_id": agent_id,
                    "display_name": AGENT_DISPLAY_NAMES.get(agent_id, agent_id),
                    "reply_text": draft_text,
                }
            )
            replies.append((agent_id, self._format_open_forum_reply(agent_id, draft_text)))
        if OPEN_FORUM_MAX_AUTONOMOUS_TURNS > 0:
            replies.extend(
                await self._run_open_forum_followups(
                    agent_ids=agent_ids,
                    message=message,
                    attachments=attachments,
                    drafts=drafts,
                    max_turns=OPEN_FORUM_MAX_AUTONOMOUS_TURNS,
                )
            )
        if not replies:
            raise RuntimeError("; ".join(failures) or "no agent reply returned")
        return replies

    async def _run_open_forum_followups(
        self,
        *,
        agent_ids: list[str],
        message: discord.Message,
        attachments: list[str],
        drafts: list[dict[str, str]],
        max_turns: int,
    ) -> list[tuple[str, str]]:
        replies: list[tuple[str, str]] = []
        if not drafts or max_turns <= 0:
            return replies
        existing_counts = self._draft_counts(drafts)
        turns_used = 0
        while turns_used < max_turns:
            progress = False
            for agent_id in agent_ids:
                if turns_used >= max_turns:
                    break
                prior_drafts = drafts[-6:]
                remaining_turns = max_turns - turns_used
                try:
                    draft_text = await self._run_chat_agent(
                        agent_id=agent_id,
                        message=message,
                        attachments=attachments,
                        prior_drafts=prior_drafts,
                        coordination_instruction=(
                            "This is a bounded autonomous follow-up window in an open forum. "
                            f"There are {remaining_turns} autonomous turn(s) remaining across all beings, including this one. "
                            "Only reply if you have something concrete to add after reading the other beings' latest messages, "
                            "especially if there is an unresolved issue, correction, direct answer, or fix commitment. "
                            "Keep it short. If this issue cannot be resolved within the remaining turns, state the blocker clearly and note what documentation or integration handoff should be recorded. "
                            "If nothing substantive needs to be added, reply with exactly NO_FOLLOWUP."
                        ),
                    )
                except Exception:
                    continue
                if self._is_no_followup(draft_text):
                    continue
                if self._is_duplicate_open_forum_reply(
                    agent_id=agent_id,
                    draft_text=draft_text,
                    drafts=drafts,
                    existing_count=existing_counts.get(agent_id, 0),
                ):
                    continue
                drafts.append(
                    {
                        "agent_id": agent_id,
                        "display_name": AGENT_DISPLAY_NAMES.get(agent_id, agent_id),
                        "reply_text": draft_text,
                    }
                )
                existing_counts[agent_id] = existing_counts.get(agent_id, 0) + 1
                replies.append((agent_id, self._format_open_forum_reply(agent_id, draft_text)))
                turns_used += 1
                progress = True
            if not progress:
                break
        return replies

    def _build_consensus_prompt(
        self,
        *,
        consensus_agent_id: str,
        message: discord.Message,
        attachments: list[str],
        drafts: list[dict[str, str]],
        draft_failures: list[dict[str, str]],
    ) -> str:
        memory_context = []
        if _memory_enabled_for_channel(getattr(message.channel, "id", None)):
            memory_context = discord_memory_context_text(
                channel_id=int(getattr(message.channel, "id", 0) or 0),
                author_name=message.author.display_name,
                exclude_message_id=int(message.id),
                limit=6,
            )
        user_context = user_context_packet_text(
            limit=4,
            context=f"{getattr(message.channel, 'name', '') or ''}\n{message.content or ''}",
            agent_id=consensus_agent_id,
            channel_name=getattr(message.channel, "name", "") or "",
        )
        lines = [
            "You are synthesizing one public reply for a shared Discord channel after reviewing private drafts from multiple beings.",
            "Return one Discord-safe message only.",
            "If the drafts align, answer with one clear consensus response.",
            "If the drafts diverge, say that briefly and resolve it into one recommended next message or prompt.",
            "Do not mention hidden drafts, internal tooling, or chain-of-thought.",
            f"Synthesis lane: {AGENT_DISPLAY_NAMES.get(consensus_agent_id, consensus_agent_id)}",
            f"Channel: #{getattr(message.channel, 'name', '') or 'unknown'}",
            f"Author: {message.author.display_name}",
            "",
            "Latest user message:",
            (message.content or "").strip() or "[no text content]",
        ]
        if user_context:
            lines.extend(["", "Operator preferences:"])
            lines.extend(user_context[:6])
        if memory_context:
            lines.extend(["", "Relevant channel context:"])
            lines.extend(memory_context[:6])
        if attachments:
            lines.extend(["", "Attachments:"])
            lines.extend(f"- {item}" for item in attachments[:5])
        lines.extend(["", "Private drafts from beings:"])
        lines.extend(
            f"- {draft['display_name']} ({draft['agent_id']}): {draft['reply_text']}"
            for draft in drafts
        )
        if draft_failures:
            lines.extend(["", "Draft failures:"])
            lines.extend(
                f"- {failure['display_name']} ({failure['agent_id']}): {failure['error']}"
                for failure in draft_failures
            )
        lines.extend(
            [
                "",
                "Produce the single best public reply for the channel now.",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _format_private_drafts(drafts: list[dict[str, str]]) -> str:
        return "\n".join(
            f"- {draft['display_name']} ({draft['agent_id']}): {draft['reply_text']}"
            for draft in drafts[-4:]
        )

    @staticmethod
    def _consensus_agent_id(agent_ids: list[str], drafts: list[dict[str, str]]) -> str:
        drafted_ids = {draft["agent_id"] for draft in drafts}
        if "discord-orchestrator" in drafted_ids:
            return "discord-orchestrator"
        for agent_id in agent_ids:
            if agent_id in drafted_ids:
                return agent_id
        return drafts[0]["agent_id"]

    def _format_multi_agent_public_reply(self, agent_ids: list[str], text: str) -> str:
        header = " + ".join(AGENT_DISPLAY_NAMES.get(agent_id, agent_id) for agent_id in agent_ids)
        body = (text or "").strip() or "Consensus pending."
        if body.lower().startswith("**consensus"):
            return body
        return f"**Consensus · {header}**\n{body}"

    def _format_open_forum_reply(self, agent_id: str, text: str) -> str:
        display_name = AGENT_DISPLAY_NAMES.get(agent_id, agent_id)
        body = (text or "").strip() or "No response text returned."
        lowered = body.lower()
        if lowered.startswith(f"**{display_name.lower()}**") or lowered.startswith(f"**{display_name.lower()} ·"):
            return body
        return f"**{display_name}**\n{body}"

    @staticmethod
    def _draft_counts(drafts: list[dict[str, str]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for draft in drafts:
            agent_id = str(draft.get("agent_id") or "").strip()
            if not agent_id:
                continue
            counts[agent_id] = counts.get(agent_id, 0) + 1
        return counts

    @staticmethod
    def _is_no_followup(text: str) -> bool:
        normalized = " ".join((text or "").strip().split()).upper()
        return normalized in {"NO_FOLLOWUP", "NO FOLLOWUP", "NO-FOLLOWUP"}

    @staticmethod
    def _is_duplicate_open_forum_reply(
        *,
        agent_id: str,
        draft_text: str,
        drafts: list[dict[str, str]],
        existing_count: int,
    ) -> bool:
        if existing_count < 1:
            return False
        normalized_new = " ".join((draft_text or "").strip().lower().split())
        if not normalized_new:
            return True
        prior_texts = [
            " ".join(str(draft.get("reply_text") or "").strip().lower().split())
            for draft in drafts
            if str(draft.get("agent_id") or "").strip() == agent_id
        ]
        return normalized_new in prior_texts

    @staticmethod
    def _fallback_consensus_text(
        *,
        drafts: list[dict[str, str]],
        draft_failures: list[dict[str, str]],
        synthesis_error: str,
    ) -> str:
        lines = [
            "Consensus synthesis degraded. Best available shared state:",
        ]
        for draft in drafts:
            lines.append(f"- {draft['display_name']}: {draft['reply_text']}")
        for failure in draft_failures:
            lines.append(f"- {failure['display_name']} unavailable: {failure['error']}")
        lines.append(f"- synthesis error: {synthesis_error}")
        return "\n".join(lines)

    @staticmethod
    def _chunk_reply(text: str, limit: int = 1900) -> list[str]:
        text = (text or "").strip()
        if not text:
            return ["No response text returned."]
        if len(text) <= limit:
            return [text]
        chunks: list[str] = []
        remaining = text
        while len(remaining) > limit:
            split_at = remaining.rfind("\n", 0, limit)
            if split_at < limit // 2:
                split_at = remaining.rfind(" ", 0, limit)
            if split_at < limit // 2:
                split_at = limit
            chunks.append(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip()
        if remaining:
            chunks.append(remaining)
        return chunks

    def _register_commands(self) -> None:
        @self.tree.command(name="ops-health", description="Show current Dali health and runtime status.")
        async def ops_health(interaction: discord.Interaction) -> None:
            if not await _ensure_allowed_channel(interaction):
                return
            await interaction.response.send_message(ops_health_text())

        @self.tree.command(name="sim-status", description="Show simulation performance and halt state.")
        @app_commands.describe(sim_id="Optional sim id such as SIM_F")
        async def sim_status(interaction: discord.Interaction, sim_id: str | None = None) -> None:
            if not await _ensure_allowed_channel(interaction):
                return
            await interaction.response.send_message(sim_status_text(sim_id))

        @self.tree.command(name="project-status", description="Show project status from the local dashboard state.")
        @app_commands.describe(project_id="Optional project id such as source-ui")
        async def project_status(interaction: discord.Interaction, project_id: str | None = None) -> None:
            if not await _ensure_allowed_channel(interaction):
                return
            await interaction.response.send_message(project_status_text(project_id))

        @self.tree.command(name="task-create", description="Create a task in the local task board.")
        @app_commands.describe(
            title="Task title",
            description="Optional task details",
            priority="Task priority",
            assignee="Optional assignee",
            project="Optional project id",
        )
        @app_commands.choices(
            priority=[app_commands.Choice(name=value, value=value) for value in ALLOWED_PRIORITIES]
        )
        async def task_create(
            interaction: discord.Interaction,
            title: str,
            description: str | None = None,
            priority: app_commands.Choice[str] | None = None,
            assignee: str | None = None,
            project: str | None = None,
        ) -> None:
            if not await _ensure_mutation_access(interaction):
                return
            message = task_create_text(
                title=title,
                description=description or "",
                priority=priority.value if priority else "medium",
                assignee=assignee or "",
                project=project or "",
            )
            await interaction.response.send_message(message)

        @self.tree.command(name="task-move", description="Move an existing task to a new status.")
        @app_commands.describe(task_id="Numeric task id", status="New task status")
        @app_commands.choices(
            status=[app_commands.Choice(name=value, value=value) for value in ALLOWED_TASK_STATUSES]
        )
        async def task_move(
            interaction: discord.Interaction,
            task_id: int,
            status: app_commands.Choice[str],
        ) -> None:
            if not await _ensure_mutation_access(interaction):
                return
            await interaction.response.send_message(task_move_text(task_id, status.value))


async def main() -> None:
    client = OpenClawDiscordBot()
    await client.start(TOKEN)


def _truncate_single_line(text: str, limit: int = 300) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 1]}…"


if __name__ == "__main__":
    asyncio.run(main())
