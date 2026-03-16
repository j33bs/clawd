import unittest
from types import SimpleNamespace

from workspace.discord_surface.bot import channel_allowed, member_can_mutate, sync_command_tree


class TestDiscordBotHelpers(unittest.TestCase):
    def test_channel_allowed_requires_explicit_allowlist_match(self):
        self.assertTrue(channel_allowed(42, {42, 43}))
        self.assertFalse(channel_allowed(99, {42, 43}))
        self.assertFalse(channel_allowed(42, set()))

    def test_member_can_mutate_uses_role_allowlist_when_set(self):
        self.assertTrue(
            member_can_mutate(role_ids={2, 3}, allowed_role_ids={3}, guild_manage=False, guild_admin=False)
        )
        self.assertFalse(
            member_can_mutate(role_ids={2}, allowed_role_ids={3}, guild_manage=True, guild_admin=True)
        )

    def test_member_can_mutate_falls_back_to_manage_or_admin(self):
        self.assertTrue(
            member_can_mutate(role_ids=set(), allowed_role_ids=set(), guild_manage=True, guild_admin=False)
        )
        self.assertTrue(
            member_can_mutate(role_ids=set(), allowed_role_ids=set(), guild_manage=False, guild_admin=True)
        )
        self.assertFalse(
            member_can_mutate(role_ids=set(), allowed_role_ids=set(), guild_manage=False, guild_admin=False)
        )

    def test_sync_command_tree_copies_global_commands_to_each_guild(self):
        events: list[tuple[str, int | None]] = []

        class FakeTree:
            def copy_global_to(self, *, guild):
                events.append(("copy", guild.id))

            async def sync(self, *, guild=None):
                events.append(("sync", None if guild is None else guild.id))

        class FakeDiscord:
            @staticmethod
            def Object(*, id):
                return SimpleNamespace(id=id)

        import asyncio

        asyncio.run(sync_command_tree(FakeTree(), guild_ids={10, 20}, discord_module=FakeDiscord))
        self.assertEqual(events, [("copy", 10), ("sync", 10), ("copy", 20), ("sync", 20)])

    def test_sync_command_tree_global_only_when_no_guilds(self):
        events: list[tuple[str, int | None]] = []

        class FakeTree:
            def copy_global_to(self, *, guild):
                events.append(("copy", guild.id))

            async def sync(self, *, guild=None):
                events.append(("sync", None if guild is None else guild.id))

        import asyncio

        asyncio.run(sync_command_tree(FakeTree(), guild_ids=set(), discord_module=None))
        self.assertEqual(events, [("sync", None)])


if __name__ == "__main__":
    unittest.main()
