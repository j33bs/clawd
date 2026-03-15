import json
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
