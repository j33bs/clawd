from __future__ import annotations

import asyncio
import traceback
from typing import Any

from .config import DiscordBotConfig
from .snapshots import (
    build_ops_snapshot,
    build_project_snapshot,
    build_sim_snapshot,
    format_ops_message,
    format_project_message,
    format_sim_message,
)
from .store import create_task, ensure_state_files, load_tasks, move_task, save_tasks

try:  # pragma: no cover - exercised only in runtime
    import discord
    from discord import app_commands
except Exception:  # pragma: no cover
    discord = None
    app_commands = None


def channel_allowed(channel_id: int | None, allowed_channel_ids: set[int]) -> bool:
    return bool(channel_id and allowed_channel_ids and int(channel_id) in allowed_channel_ids)


def member_can_mutate(
    *,
    role_ids: set[int],
    allowed_role_ids: set[int],
    guild_manage: bool,
    guild_admin: bool,
) -> bool:
    if allowed_role_ids:
        return bool(role_ids & allowed_role_ids)
    return bool(guild_manage or guild_admin)


async def sync_command_tree(tree: Any, *, guild_ids: set[int], discord_module: Any) -> None:
    if guild_ids:
        for guild_id in guild_ids:
            guild = discord_module.Object(id=guild_id)
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
        return
    await tree.sync()


async def run_bot(config: DiscordBotConfig) -> None:  # pragma: no cover - runtime only
    if discord is None or app_commands is None:
        raise RuntimeError("discord.py is not installed in the runtime venv")
    if not config.token:
        raise RuntimeError("OPENCLAW_DISCORD_BOT_TOKEN is required")
    ensure_state_files(config.tasks_path, config.projects_path, config.bridge_state_path)

    intents = discord.Intents.none()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    commands_synced = False

    async def _deny(interaction: discord.Interaction, message: str) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def _defer(interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

    async def _respond(interaction: discord.Interaction, message: str) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    def _who(interaction: discord.Interaction) -> str:
        user_id = getattr(getattr(interaction, "user", None), "id", "unknown")
        channel_id = getattr(interaction, "channel_id", "unknown")
        return f"user={user_id} channel={channel_id}"

    def _role_ids(interaction: discord.Interaction) -> set[int]:
        roles = getattr(interaction.user, "roles", []) or []
        return {int(role.id) for role in roles if getattr(role, "id", None) is not None}

    def _guild_manage(interaction: discord.Interaction) -> bool:
        perms = getattr(interaction.user, "guild_permissions", None)
        return bool(getattr(perms, "manage_guild", False))

    def _guild_admin(interaction: discord.Interaction) -> bool:
        perms = getattr(interaction.user, "guild_permissions", None)
        return bool(getattr(perms, "administrator", False))

    async def _require_read_channel(interaction: discord.Interaction) -> bool:
        if channel_allowed(interaction.channel_id, config.allowed_channel_ids):
            return True
        await _deny(interaction, "This command is allowed only in configured Discord channels.")
        return False

    async def _require_mutation_perms(interaction: discord.Interaction) -> bool:
        if not await _require_read_channel(interaction):
            return False
        if member_can_mutate(
            role_ids=_role_ids(interaction),
            allowed_role_ids=config.mutation_role_ids,
            guild_manage=_guild_manage(interaction),
            guild_admin=_guild_admin(interaction),
        ):
            return True
        await _deny(interaction, "You do not have permission to mutate local task state.")
        return False

    @tree.command(name="ops-health", description="Show compact local ops health from file-backed state.")
    async def ops_health(interaction: discord.Interaction) -> None:
        print(f"discord_cmd_start name=ops-health {_who(interaction)}")
        if not await _require_read_channel(interaction):
            return
        await _defer(interaction)
        snapshot = build_ops_snapshot(
            tasks_path=config.tasks_path,
            projects_path=config.projects_path,
            sim_path=config.sim_path,
            health_services=config.health_services,
            log_paths=config.log_paths,
        )
        await _respond(interaction, format_ops_message(snapshot))
        print(f"discord_cmd_ok name=ops-health {_who(interaction)}")

    @tree.command(name="sim-status", description="Show compact sim status from local JSON.")
    async def sim_status(interaction: discord.Interaction) -> None:
        print(f"discord_cmd_start name=sim-status {_who(interaction)}")
        if not await _require_read_channel(interaction):
            return
        await _defer(interaction)
        await _respond(interaction, format_sim_message(build_sim_snapshot(config.sim_path)))
        print(f"discord_cmd_ok name=sim-status {_who(interaction)}")

    @tree.command(name="project-status", description="Show compact project/task summary from local JSON.")
    async def project_status(interaction: discord.Interaction) -> None:
        print(f"discord_cmd_start name=project-status {_who(interaction)}")
        if not await _require_read_channel(interaction):
            return
        await _defer(interaction)
        snapshot = build_project_snapshot(config.tasks_path, config.projects_path)
        await _respond(interaction, format_project_message(snapshot))
        print(f"discord_cmd_ok name=project-status {_who(interaction)}")

    @tree.command(name="task-create", description="Create a task in the local task JSON store.")
    @app_commands.describe(title="Task title", project="Project id or name", details="Optional details")
    async def task_create(interaction: discord.Interaction, title: str, project: str = "", details: str = "") -> None:
        print(f"discord_cmd_start name=task-create {_who(interaction)}")
        if not await _require_mutation_perms(interaction):
            return
        await _defer(interaction)
        tasks_doc = load_tasks(config.tasks_path)
        task = create_task(
            tasks_doc,
            title=title,
            project=project or "default",
            details=details,
            created_by=str(interaction.user.id),
        )
        save_tasks(config.tasks_path, tasks_doc)
        await _respond(
            interaction,
            f"task-created {task['id']} status={task['status']} project={task['project']} title={task['title']}",
        )
        print(f"discord_cmd_ok name=task-create {_who(interaction)}")

    @tree.command(name="task-move", description="Move a task to a new local status.")
    @app_commands.describe(task_id="Task id", status="New status such as todo, in_progress, blocked, done")
    async def task_move(interaction: discord.Interaction, task_id: str, status: str) -> None:
        print(f"discord_cmd_start name=task-move {_who(interaction)}")
        if not await _require_mutation_perms(interaction):
            return
        await _defer(interaction)
        tasks_doc = load_tasks(config.tasks_path)
        try:
            task = move_task(tasks_doc, task_id=task_id, status=status, moved_by=str(interaction.user.id))
        except KeyError:
            await _deny(interaction, f"Task not found: {task_id}")
            return
        save_tasks(config.tasks_path, tasks_doc)
        await _respond(
            interaction,
            f"task-moved {task['id']} status={task['status']} title={task['title']}",
        )
        print(f"discord_cmd_ok name=task-move {_who(interaction)}")

    @tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        print(f"discord_cmd_error name={getattr(getattr(interaction, 'command', None), 'name', 'unknown')} {_who(interaction)}")
        traceback.print_exception(type(error), error, error.__traceback__)
        await _deny(interaction, "Command failed inside c_lawd. Check local bot logs.")

    @client.event
    async def on_ready() -> None:
        nonlocal commands_synced
        if not commands_synced:
            await sync_command_tree(tree, guild_ids=config.guild_ids, discord_module=discord)
            commands_synced = True
            print(f"discord_ready user={getattr(client.user, 'id', 'unknown')} guilds={sorted(config.guild_ids)} synced=1")
            return
        print(f"discord_ready user={getattr(client.user, 'id', 'unknown')} guilds={sorted(config.guild_ids)} synced=0")

    await client.start(config.token)


def main_sync(config: DiscordBotConfig) -> None:  # pragma: no cover - runtime only
    asyncio.run(run_bot(config))
