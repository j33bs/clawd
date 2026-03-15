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

from api.discord_bot_support import (  # noqa: E402
    build_discord_chat_prompt,
    discord_memory_context_text,
    extract_agent_reply_text,
    extract_last_json_object,
    parse_channel_agent_map,
    project_status_text,
    prompt_harness_for_agent,
    sim_status_text,
    task_move_text,
    user_context_packet_text,
)
from api.task_store import save_tasks  # noqa: E402


class TestDiscordBotSupport(unittest.TestCase):
    def test_parse_channel_agent_map_ignores_bad_entries(self):
        mapping = parse_channel_agent_map("148=discord-gpt54, bad, 149 = discord-codex53 ,x=y")
        self.assertEqual(mapping, {148: "discord-gpt54", 149: "discord-codex53"})

    def test_build_discord_chat_prompt_includes_context(self):
        prompt = build_discord_chat_prompt(
            agent_id="discord-gpt54",
            author_name="Heath",
            channel_name="gpt54-chat",
            content="What's live?",
            attachments=["https://example.com/chart.png"],
            user_context=["- Prefer concise, direct operational responses by default."],
            memory_context=["- 2026-03-10 #gpt54-chat: prefers concise sim summaries"],
        )
        self.assertIn("Channel: #gpt54-chat", prompt)
        self.assertIn("Author: Heath", prompt)
        self.assertIn("What's live?", prompt)
        self.assertIn("chart.png", prompt)
        self.assertIn("User operating preferences:", prompt)
        self.assertIn("Relevant remembered context:", prompt)

    def test_build_discord_chat_prompt_includes_relational_context(self):
        with mock.patch(
            "api.discord_bot_support.build_relational_prompt_lines",
            return_value=["- Mode: repair.", "- Acknowledge friction before redirecting."],
        ):
            prompt = build_discord_chat_prompt(
                agent_id="discord-gpt54",
                author_name="Heath",
                channel_name="gpt54-chat",
                content="What's live?",
                attachments=[],
                user_context=[],
                memory_context=[],
            )
        self.assertIn("Current relational state:", prompt)
        self.assertIn("Mode: repair.", prompt)
        self.assertIn("Acknowledge friction before redirecting.", prompt)

    def test_prompt_harness_for_agent_uses_codex_profile(self):
        harness = prompt_harness_for_agent("discord-codex53")
        self.assertEqual(harness["name"], "codex53_build_operator")

    def test_build_discord_chat_prompt_uses_codex_harness(self):
        prompt = build_discord_chat_prompt(
            agent_id="discord-codex53",
            author_name="Heath",
            channel_name="codex-chat",
            content="Refactor the bridge.",
            attachments=[],
            user_context=["- Prefer concise, direct operational responses by default."],
            memory_context=["- Previous bridge work focused on dedupe."],
        )
        self.assertIn("using Codex 5.3", prompt)
        self.assertIn("Operator constraints:", prompt)
        self.assertIn("Prior engineering context:", prompt)

    def test_build_discord_chat_prompt_uses_minimax_harness(self):
        prompt = build_discord_chat_prompt(
            agent_id="discord-minimax25",
            author_name="Heath",
            channel_name="minimax-chat",
            content="Think through this research direction.",
            attachments=[],
            user_context=["- Prefer concise, direct operational responses by default."],
            memory_context=["- Prior context entry."],
        )
        self.assertIn("using MiniMax M2.5", prompt)
        self.assertIn("Personalization signals:", prompt)
        self.assertIn("Relevant remembered context:", prompt)

    def test_discord_memory_context_text_delegates_to_memory_builder(self):
        with mock.patch("api.discord_bot_support.build_discord_memory_context", return_value=["- memory"]) as mocked:
            context = discord_memory_context_text(channel_id=148, author_name="jeebs", exclude_message_id=2, limit=3)
        self.assertEqual(context, ["- memory"])
        mocked.assert_called_once()

    def test_user_context_packet_text_delegates_to_inference_builder(self):
        with mock.patch("api.discord_bot_support.query_preference_graph", return_value={"prompt_lines": []}):
            with mock.patch("api.discord_bot_support.build_user_context_packet", return_value=["- concise"]) as mocked:
                context = user_context_packet_text(limit=3)
        self.assertEqual(context, ["- concise"])
        mocked.assert_called_once_with(limit=3, context="", profile_sections=None)

    def test_extract_last_json_object_finds_trailing_payload(self):
        payload = extract_last_json_object("noise\n{\"payloads\":[{\"text\":\"ok\"}]}")
        self.assertEqual(payload["payloads"][0]["text"], "ok")

    def test_extract_agent_reply_text_joins_payloads(self):
        text = extract_agent_reply_text(
            {
                "payloads": [
                    {"text": "one"},
                    {"text": "two"},
                ]
            }
        )
        self.assertEqual(text, "one\n\ntwo")

    def test_sim_status_text_handles_specific_sim(self):
        with mock.patch(
            "api.discord_bot_support.portfolio_payload",
            return_value={
                "sims": [
                    {
                        "id": "SIM_I",
                        "display_name": "US Equity Event Impulse",
                        "active_book": True,
                        "live_equity": 300.0,
                        "live_equity_change": 0.0,
                        "live_return_pct": 0.0,
                        "round_trips": 0,
                        "win_rate": 0.0,
                        "open_positions": 0,
                        "stage": "paper_live",
                        "control_lane": False,
                    }
                ],
                "sim_strategy_review": {
                    "recommendations": [
                        {
                            "id": "SIM_I",
                            "recommendation": "retune",
                        }
                    ]
                },
            },
        ):
            text = sim_status_text("SIM_I")
        self.assertIn("US Equity Event Impulse", text)
        self.assertIn("capital $300.00", text)
        self.assertIn("retune", text)

    def test_project_status_text_handles_unknown_project(self):
        text = project_status_text("missing-project")
        self.assertIn("No projects matched", text)

    def test_task_move_text_updates_task_store(self):
        with tempfile.TemporaryDirectory() as td:
            tasks_path = Path(td) / "tasks.json"
            save_tasks(
                [
                    {
                        "id": 42,
                        "title": "Discord bot test",
                        "status": "backlog",
                        "priority": "medium",
                        "project": "source-ui",
                        "assignee": "coder",
                    }
                ],
                path=tasks_path,
            )
            from api import discord_bot_support as support  # noqa: E402

            with mock.patch.object(
                support,
                "update_task",
                side_effect=lambda task_id, updates: __import__("api.task_store", fromlist=["update_task"]).update_task(
                    task_id, updates, path=tasks_path
                ),
            ):
                message = support.task_move_text(42, "done")

            self.assertIn("Task Updated", message)
            self.assertRegex(message, r"(done|in_progress)")


if __name__ == "__main__":
    unittest.main()
