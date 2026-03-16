import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api import task_store  # noqa: E402


class TaskStoreRuntimeTests(unittest.TestCase):
    def test_load_runtime_tasks_extracts_live_session_work(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            agents_root = root / "agents"
            sessions_dir = agents_root / "codex" / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            session_id = "abc123"
            sessions_path = sessions_dir / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:codex:main": {
                            "sessionId": session_id,
                            "updatedAt": 1773387000000,
                            "model": "openai-codex/gpt-5.3-codex",
                            "label": "Codex live session",
                        }
                    }
                ),
                encoding="utf-8",
            )
            (sessions_dir / f"{session_id}.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "message",
                                "message": {
                                    "role": "assistant",
                                    "content": [{"type": "text", "text": "**Task**: tighten Source UI runtime queue"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "message",
                                "message": {
                                    "role": "assistant",
                                    "content": [{"type": "text", "text": "Currently wiring live Codex sessions into tasks."}],
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(task_store, "_local_node_id", return_value="dali"):
                rows = task_store.load_runtime_tasks(
                    agents_root=agents_root,
                    subagent_runs_path=root / "subagents" / "runs.json",
                    lookback_hours=240,
                )

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["node_id"], "dali")
            self.assertEqual(rows[0]["assignee"], "codex")
            self.assertTrue(rows[0]["read_only"])
            self.assertIn("tighten Source UI runtime queue", rows[0]["title"])
            self.assertEqual(rows[0]["runtime_source_label"], "live session")

    def test_load_all_tasks_merges_remote_runtime_tasks_read_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / "tasks.json"
            tasks_path.write_text(
                json.dumps([{"id": 1001, "title": "Local task", "status": "backlog", "priority": "medium"}]),
                encoding="utf-8",
            )
            sources_path = root / "runtime_task_sources.json"
            sources_path.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "c_lawd",
                                "label": "c_lawd",
                                "enabled": True,
                                "url": "https://clawd.tail5e5706.ts.net:10000/api/runtime-tasks",
                                "timeout_s": 0.1,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(
                        {
                            "tasks": [
                                {
                                    "id": "codex:remote123",
                                    "title": "Remote Codex task",
                                    "status": "in_progress",
                                    "priority": "high",
                                    "assignee": "codex",
                                    "runtime_source_label": "live session",
                                }
                            ]
                        }
                    ).encode("utf-8")

            with mock.patch.object(task_store.urllib.request, "urlopen", return_value=FakeResponse()):
                with mock.patch.object(task_store, "SOURCE_MISSION_CONFIG_PATH", root / "missing-source-mission.json"):
                    rows = task_store.load_all_tasks(
                        path=tasks_path,
                        agents_root=root / "agents",
                        subagent_runs_path=root / "subagents" / "runs.json",
                        runtime_sources_path=sources_path,
                        lookback_hours=1,
                    )

            self.assertEqual(len(rows), 2)
            remote = next(item for item in rows if str(item["id"]).startswith("runtime:c-lawd:"))
            self.assertEqual(remote["node_label"], "c_lawd")
            self.assertTrue(remote["read_only"])
            self.assertEqual(remote["title"], "Remote Codex task")

    def test_load_runtime_tasks_skips_direct_chat_sessions_without_explicit_task_hint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            agents_root = root / "agents"
            sessions_dir = agents_root / "main" / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            session_id = "direct123"
            (sessions_dir / "sessions.json").write_text(
                json.dumps(
                    {
                        "agent:main:main": {
                            "sessionId": session_id,
                            "updatedAt": 1773387000000,
                            "model": "MiniMax-M2.5",
                            "chatType": "direct",
                            "lastChannel": "telegram",
                            "label": "Telegram operator chat",
                        }
                    }
                ),
                encoding="utf-8",
            )
            (sessions_dir / f"{session_id}.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "message",
                                "message": {
                                    "role": "user",
                                    "content": [{"type": "text", "text": "i dont want have to mark anything"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "message",
                                "message": {
                                    "role": "assistant",
                                    "content": [{"type": "text", "text": "Done, no buttons needed."}],
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            rows = task_store.load_runtime_tasks(
                agents_root=agents_root,
                subagent_runs_path=root / "subagents" / "runs.json",
                lookback_hours=240,
            )

            self.assertEqual(rows, [])

    def test_load_runtime_source_health_reports_unreachable_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sources_path = root / "runtime_task_sources.json"
            sources_path.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "c_lawd",
                                "label": "c_lawd",
                                "enabled": True,
                                "url": "http://127.0.0.1:65500/api/runtime-tasks",
                                "timeout_s": 0.1,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            task_store._REMOTE_TASK_CACHE.clear()
            with mock.patch.object(
                task_store.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("[Errno 111] Connection refused"),
            ):
                rows = task_store.load_runtime_source_health(runtime_sources_path=sources_path)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "warning")
            self.assertIn("Connection refused", rows[0]["details"])

    def test_load_tasks_archives_done_task_even_when_archive_already_has_same_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / "tasks.json"
            archive_path = root / "archived_tasks.json"
            tasks_path.write_text(
                json.dumps(
                    [
                        {
                            "id": 1001,
                            "title": "Joyful Source UI cleanup",
                            "status": "done",
                            "priority": "medium",
                            "completed_at": "2026-03-01T00:00:00Z",
                            "updated_at": "2026-03-01T00:00:00Z",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            archive_path.write_text(
                json.dumps(
                    [
                        {
                            "id": 1001,
                            "title": "Older archived copy",
                            "status": "archived",
                            "archived_at": "2026-02-01T00:00:00Z",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(task_store, "ARCHIVED_TASKS_PATH", archive_path):
                with mock.patch.object(task_store, "SOURCE_MISSION_CONFIG_PATH", root / "missing-source-mission.json"):
                    with mock.patch.object(task_store, "_task_requires_review_gate", return_value=False):
                        rows = task_store.load_tasks(path=tasks_path)

            self.assertEqual(rows, [])
            archived_rows = json.loads(archive_path.read_text(encoding="utf-8"))
            self.assertEqual(len(archived_rows), 1)
            self.assertEqual(archived_rows[0]["status"], "archived")
            self.assertEqual(archived_rows[0]["title"], "Joyful Source UI cleanup")
            self.assertIn("archived_at", archived_rows[0])

    def test_load_tasks_restores_archived_source_mission_task_when_it_is_not_done(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / "tasks.json"
            archive_path = root / "archived_tasks.json"
            source_mission_path = root / "source_mission.json"
            tasks_path.write_text("[]\n", encoding="utf-8")
            archive_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "sm-001",
                            "title": "Weekly Evolution Loop",
                            "status": "archived",
                            "mission_task_id": "source-009",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            source_mission_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "source-009",
                                "title": "Weekly Evolution Loop",
                                "pillar": "evolve",
                                "priority": "medium",
                                "summary": "Add a scheduled review that summarizes what the collective learned.",
                                "definition_of_done": "Source produces a concise weekly evolution report with wins, regressions, and top three upgrades.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            fake_signals = {
                "has_weekly_evolution_report": False,
                "has_weekly_evolution_scheduler": False,
                "has_weekly_evolution_ui": False,
                "runtime_claims": {},
            }

            with mock.patch.object(task_store, "ARCHIVED_TASKS_PATH", archive_path):
                with mock.patch.object(task_store, "SOURCE_MISSION_CONFIG_PATH", source_mission_path):
                    with mock.patch.object(task_store, "_source_mission_signals", return_value=fake_signals):
                        with mock.patch.object(task_store, "_source_mission_ingest_state", return_value={}):
                            rows = task_store.load_tasks(path=tasks_path)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], "sm-001")
            self.assertEqual(rows[0]["status"], "backlog")
            self.assertEqual(rows[0]["mission_task_id"], "source-009")

    def test_next_task_id_avoids_reusing_archived_numeric_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive_path = root / "archived_tasks.json"
            archive_path.write_text(
                json.dumps(
                    [
                        {"id": 1001, "title": "older"},
                        {"id": 1004, "title": "latest"},
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(task_store, "ARCHIVED_TASKS_PATH", archive_path):
                next_id = task_store.next_task_id([{"id": 1002}, {"id": "1003"}])

            self.assertEqual(next_id, 1005)


if __name__ == "__main__":
    unittest.main()
