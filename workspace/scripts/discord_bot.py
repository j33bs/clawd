#!/usr/bin/env python3
"""Discord bot for OpenClaw project/status commands."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
for path in (SOURCE_UI_ROOT, REPO_ROOT):
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
        lock = self._channel_locks.setdefault(channel_id, asyncio.Lock())
        for agent_id in agent_ids:
            async with lock:
                try:
                    async with message.channel.typing():
                        reply_text = await self._run_chat_agent(
                            agent_id=agent_id,
                            message=message,
                            attachments=attachment_urls,
                        )
                except asyncio.TimeoutError:
                    await message.reply(f"[{agent_id}] Timed out waiting for the model.", mention_author=False)
                    continue
                except Exception as exc:
                    await message.reply(f"[{agent_id}] Model call failed: {exc}", mention_author=False)
                    continue
            if _memory_enabled_for_channel(channel_id):
                try:
                    ingest_discord_exchange(
                        guild_id=getattr(message.guild, "id", None),
                        guild_name=getattr(message.guild, "name", "") or "",
                        channel_id=channel_id,
                        channel_name=getattr(message.channel, "name", "") or "",
                        message_id=f"{message.id}:assistant:{agent_id}",
                        author_id=getattr(self.user, "id", None),
                        author_name=getattr(self.user, "display_name", None) or getattr(self.user, "name", "Dali"),
                        role="assistant",
                        content=reply_text,
                        attachments=[],
                        created_at="",
                        agent_scope=MEMORY_AGENT_SCOPE,
                        agent_id=agent_id,
                        ingest_research=_research_enabled_for_channel(channel_id),
                    )
                except Exception as exc:
                    print(f"discord memory ingest failed for assistant reply ({agent_id}): {exc}")
            # Prefix with display name when multiple agents share the channel
            _multi_agent = len(agent_ids) > 1
            _display = AGENT_DISPLAY_NAMES.get(agent_id, agent_id) if _multi_agent else None
            chunks = self._chunk_reply(reply_text)
            for i, chunk in enumerate(chunks):
                if i == 0 and _display:
                    chunk = f"**{_display}**\n{chunk}"
                await message.reply(chunk, mention_author=False)

    async def _run_chat_agent(
        self,
        *,
        agent_id: str,
        message: discord.Message,
        attachments: list[str],
    ) -> str:
        memory_context = []
        if _memory_enabled_for_channel(getattr(message.channel, "id", None)):
            memory_context = discord_memory_context_text(
                channel_id=int(getattr(message.channel, "id", 0) or 0),
                author_name=message.author.display_name,
                exclude_message_id=int(message.id),
                limit=4,
            )
        user_context = user_context_packet_text(limit=4)
        prompt = build_discord_chat_prompt(
            agent_id=agent_id,
            author_name=message.author.display_name,
            channel_name=getattr(message.channel, "name", "") or "",
            content=message.content or "",
            attachments=attachments,
            memory_context=memory_context,
            user_context=user_context,
        )
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
