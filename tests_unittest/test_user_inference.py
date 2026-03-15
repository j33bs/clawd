import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api import user_inference  # noqa: E402


class TestUserInference(unittest.TestCase):
    def test_distill_user_inferences_builds_profile(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            discord_path = data_dir / "discord_messages.jsonl"
            telegram_path = data_dir / "telegram_messages.jsonl"
            out_jsonl = data_dir / "user_inferences.jsonl"
            out_profile = data_dir / "preference_profile.json"

            discord_rows = [
                {
                    "role": "user",
                    "channel_id": "148",
                    "message_id": "1",
                    "created_at": "2026-03-11T10:00:00Z",
                    "content": "Prefer concise operational summaries.",
                },
                {
                    "role": "user",
                    "channel_id": "148",
                    "message_id": "2",
                    "created_at": "2026-03-11T11:00:00Z",
                    "content": "Sim reports should be in coherent professional format with key information only.",
                },
            ]
            telegram_rows = [
                {
                    "role": "user",
                    "chat_id": "8159253715",
                    "message_id": "3",
                    "created_at": "2026-03-11T12:00:00Z",
                    "content": "Just cron audits and checks, don't need to see them.",
                }
            ]
            discord_path.write_text("".join(json.dumps(row) + "\n" for row in discord_rows), encoding="utf-8")
            telegram_path.write_text("".join(json.dumps(row) + "\n" for row in telegram_rows), encoding="utf-8")

            with mock.patch.object(user_inference, "DISCORD_MEMORY_PATH", discord_path):
                with mock.patch.object(user_inference, "TELEGRAM_MEMORY_PATH", telegram_path):
                    with mock.patch.object(user_inference, "USER_INFERENCES_PATH", out_jsonl):
                        with mock.patch.object(user_inference, "PREFERENCE_PROFILE_PATH", out_profile):
                            result = user_inference.distill_user_inferences()
                            packet = user_inference.build_user_context_packet(limit=5)

            self.assertEqual(result["inference_count"], 3)
            profile = json.loads(out_profile.read_text(encoding="utf-8"))
            self.assertTrue(profile["communication"]["concise_default"]["value"])
            self.assertTrue(profile["notifications"]["suppress_routine_ops"]["value"])
            self.assertTrue(any("key information" in line.lower() for line in packet))

    def test_sync_preference_packet_to_workspaces_updates_user_md(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "data"
            data_dir.mkdir()
            discord_path = data_dir / "discord_messages.jsonl"
            telegram_path = data_dir / "telegram_messages.jsonl"
            out_jsonl = data_dir / "user_inferences.jsonl"
            out_profile = data_dir / "preference_profile.json"
            workspace_a = root / "workspace-a"
            workspace_b = root / "workspace-b"
            workspace_a.mkdir()
            workspace_b.mkdir()
            (workspace_a / "USER.md").write_text("# USER\n\nExisting.\n", encoding="utf-8")
            (workspace_b / "USER.md").write_text("# USER\n\nExisting.\n", encoding="utf-8")
            cfg_path = root / "openclaw.json"
            cfg_path.write_text(
                json.dumps(
                    {
                        "agents": {
                            "list": [
                                {"id": "a", "workspace": str(workspace_a)},
                                {"id": "b", "workspace": str(workspace_b)},
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            discord_rows = [
                {
                    "role": "user",
                    "channel_id": "148",
                    "message_id": "1",
                    "created_at": "2026-03-11T10:00:00Z",
                    "content": "Prefer concise operational summaries.",
                }
            ]
            discord_path.write_text("".join(json.dumps(row) + "\n" for row in discord_rows), encoding="utf-8")
            telegram_path.write_text("", encoding="utf-8")

            with mock.patch.object(user_inference, "DISCORD_MEMORY_PATH", discord_path):
                with mock.patch.object(user_inference, "TELEGRAM_MEMORY_PATH", telegram_path):
                    with mock.patch.object(user_inference, "USER_INFERENCES_PATH", out_jsonl):
                        with mock.patch.object(user_inference, "PREFERENCE_PROFILE_PATH", out_profile):
                            user_inference.distill_user_inferences()
                            result = user_inference.sync_preference_packet_to_workspaces(config_path=cfg_path, limit=4)

            self.assertEqual(result["workspace_count"], 2)
            self.assertTrue((workspace_a / "PREFERENCE_PACKET.md").exists())
            self.assertIn("Distilled Preferences", (workspace_a / "USER.md").read_text(encoding="utf-8"))
            self.assertIn("Prefer concise", (workspace_b / "USER.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
