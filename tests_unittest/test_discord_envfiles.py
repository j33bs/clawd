import tempfile
import unittest
from pathlib import Path

from workspace.discord_surface.envfiles import load_env_file, parse_env_text, write_env_file


class TestDiscordEnvfiles(unittest.TestCase):
    def test_parse_env_text_handles_quotes_and_spaces(self):
        payload = parse_env_text(
            'OPENCLAW_DISCORD_ALLOWED_CHANNEL_IDS=1,2,3\n'
            'OPENCLAW_DISCORD_LOG_PATHS="/tmp/one log,/tmp/two"\n'
            "export OPENCLAW_NAME='c_lawd discord'\n"
        )
        self.assertEqual(payload["OPENCLAW_DISCORD_ALLOWED_CHANNEL_IDS"], "1,2,3")
        self.assertEqual(payload["OPENCLAW_DISCORD_LOG_PATHS"], "/tmp/one log,/tmp/two")
        self.assertEqual(payload["OPENCLAW_NAME"], "c_lawd discord")

    def test_write_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "discord.env"
            write_env_file(
                path,
                {
                    "OPENCLAW_DISCORD_BOT_TOKEN": "abc 123",
                    "OPENCLAW_DISCORD_ALLOWED_CHANNEL_IDS": "1,2",
                },
            )
            loaded = load_env_file(path)
            self.assertEqual(loaded["OPENCLAW_DISCORD_BOT_TOKEN"], "abc 123")
            self.assertEqual(loaded["OPENCLAW_DISCORD_ALLOWED_CHANNEL_IDS"], "1,2")


if __name__ == "__main__":
    unittest.main()

