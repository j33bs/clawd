import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "source_backlog_ingest.py"
_SPEC = importlib.util.spec_from_file_location("_source_backlog_ingest", _SCRIPT)
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["_source_backlog_ingest"] = _MOD
_SPEC.loader.exec_module(_MOD)


class TestDispatchPrompt(unittest.TestCase):
    def test_prompt_contains_markers_and_task_identity(self):
        prompt = _MOD._dispatch_prompt(
            {
                "id": "sm-008",
                "mission_task_id": "source-008",
                "title": "Consent and Provenance Boundary Map",
                "status_reason": "Queued for c_lawd",
                "definition_of_done": "Boundary map is implemented and wired.",
            },
            route={"stage_kind": "chat_main"},
        )

        self.assertIn("sm-008 / source-008 - Consent and Provenance Boundary Map", prompt)
        self.assertIn("BACKLOG_RESULT:", prompt)
        self.assertIn("BACKLOG_BLOCKER:", prompt)
        self.assertIn("Do not reply with acknowledgement only.", prompt)

    def test_repo_prompt_requires_result_artifact(self):
        prompt = _MOD._dispatch_prompt(
            {
                "id": "sm-005",
                "mission_task_id": "source-005",
                "assignee": "c_lawd",
                "title": "Relational State Layer",
                "status_reason": "Sandbox blocker needs repo-capable execution",
                "definition_of_done": "Relational state is implemented in UI and harness.",
            },
            route={
                "stage_kind": "repo_acp",
                "result_path": "/tmp/backlog-result.json",
            },
        )

        self.assertIn("repo-capable Codex ACP session", prompt)
        self.assertIn("/tmp/backlog-result.json", prompt)
        self.assertIn('"kind"', prompt)


class TestStageIngestSession(unittest.TestCase):
    def test_stage_dispatches_into_main_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_root = Path(tmpdir)
            sessions_dir = agents_root / "discord-clawd" / "sessions"
            sessions_dir.mkdir(parents=True)
            session_log = sessions_dir / "main-session.jsonl"
            session_log.write_text("", encoding="utf-8")
            sessions_path = sessions_dir / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:discord-clawd:main": {
                            "sessionId": "main-session",
                            "sessionFile": str(session_log),
                            "updatedAt": 1773536639259,
                        }
                    }
                ),
                encoding="utf-8",
            )

            calls: list[list[str]] = []

            def fake_run(cmd, **kwargs):
                calls.append(cmd)

                class Result:
                    returncode = 0
                    stdout = json.dumps({"runId": "run-123", "status": "started"})
                    stderr = ""

                return Result()

            with patch.object(_MOD, "AGENTS_ROOT", agents_root), patch.object(_MOD.subprocess, "run", side_effect=fake_run):
                staged = _MOD._stage_ingest_session(
                    {
                        "runtime_agent": "discord-clawd",
                        "session_key": "agent:discord-clawd:main",
                        "session_file": str(session_log),
                        "stage_kind": "chat_main",
                        "result_path": "",
                    },
                    {
                        "id": "sm-008",
                        "mission_task_id": "source-008",
                        "title": "Consent and Provenance Boundary Map",
                        "status_reason": "Queued for c_lawd",
                        "definition_of_done": "Boundary map is implemented and wired.",
                    },
                )

            self.assertEqual(staged["session_key"], "agent:discord-clawd:main")
            self.assertEqual(staged["run_id"], "run-123")
            self.assertTrue(staged["idempotency_key"].startswith("source-backlog:discord-clawd:sm-008:"))
            self.assertEqual(staged["session_file"], str(session_log))
            self.assertEqual(calls[0][:5], ["openclaw", "gateway", "call", "chat.send", "--json"])

    def test_stage_accepts_empty_stdout_when_session_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_root = Path(tmpdir)
            sessions_dir = agents_root / "discord-clawd" / "sessions"
            sessions_dir.mkdir(parents=True)
            session_log = sessions_dir / "main-session.jsonl"
            session_log.write_text("", encoding="utf-8")
            sessions_path = sessions_dir / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:discord-clawd:main": {
                            "sessionId": "main-session",
                            "sessionFile": str(session_log),
                            "updatedAt": 10,
                        }
                    }
                ),
                encoding="utf-8",
            )

            def fake_run(cmd, **kwargs):
                sessions_path.write_text(
                    json.dumps(
                        {
                            "agent:discord-clawd:main": {
                                "sessionId": "main-session",
                                "sessionFile": str(session_log),
                                "updatedAt": 20,
                            }
                        }
                    ),
                    encoding="utf-8",
                )

                class Result:
                    returncode = 0
                    stdout = ""
                    stderr = ""

                return Result()

            with patch.object(_MOD, "AGENTS_ROOT", agents_root), patch.object(_MOD.subprocess, "run", side_effect=fake_run):
                staged = _MOD._stage_ingest_session(
                    {
                        "runtime_agent": "discord-clawd",
                        "session_key": "agent:discord-clawd:main",
                        "session_file": str(session_log),
                        "stage_kind": "chat_main",
                        "result_path": "",
                    },
                    {
                        "id": "sm-008",
                        "mission_task_id": "source-008",
                        "title": "Consent and Provenance Boundary Map",
                        "status_reason": "Queued for c_lawd",
                        "definition_of_done": "Boundary map is implemented and wired.",
                    },
                )

            self.assertEqual(staged["run_id"], "")

    def test_stage_accepts_gateway_banner_before_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_root = Path(tmpdir)
            sessions_dir = agents_root / "codex" / "sessions"
            sessions_dir.mkdir(parents=True)
            session_log = sessions_dir / "repo-session.jsonl"
            session_log.write_text("", encoding="utf-8")
            sessions_path = sessions_dir / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:codex:acp:repo-session": {
                            "sessionId": "repo-session",
                            "sessionFile": str(session_log),
                            "updatedAt": 1773536639259,
                            "acp": {
                                "agent": "codex",
                                "cwd": str(REPO_ROOT),
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            def fake_run(cmd, **kwargs):
                class Result:
                    returncode = 0
                    stdout = (
                        "openclaw_gateway build_sha=237e312 version=2026.3.13 "
                        "build_time=2026-02-24T06:23:42Z\n"
                        '{\n  "runId": "run-456",\n  "status": "started"\n}'
                    )
                    stderr = ""

                return Result()

            with patch.object(_MOD, "AGENTS_ROOT", agents_root), patch.object(
                _MOD.subprocess, "run", side_effect=fake_run
            ):
                staged = _MOD._stage_ingest_session(
                    {
                        "runtime_agent": "codex",
                        "session_key": "agent:codex:acp:repo-session",
                        "session_file": str(session_log),
                        "stage_kind": "repo_acp",
                        "result_path": str(Path(tmpdir) / "result.json"),
                    },
                    {
                        "id": "sm-005",
                        "mission_task_id": "source-005",
                        "title": "Relational State Layer",
                        "status_reason": "Awaiting repo-backed work",
                        "definition_of_done": "Relational signals are wired through UI and harnesses.",
                    },
                )

            self.assertEqual(staged["run_id"], "run-456")


class TestExtractIngestOutcome(unittest.TestCase):
    def test_returns_none_when_main_session_log_is_missing(self):
        with patch.object(_MOD, "_main_session_log", return_value=None):
            outcome = _MOD._extract_ingest_outcome("discord-clawd", staged_at=0.0)

        self.assertIsNone(outcome)

    def test_extracts_only_recent_marker_from_main_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_root = Path(tmpdir)
            sessions_dir = agents_root / "discord-clawd" / "sessions"
            sessions_dir.mkdir(parents=True)
            session_log = sessions_dir / "main-session.jsonl"
            session_log.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "message",
                                "timestamp": "2026-03-15T01:00:00Z",
                                "message": {
                                    "role": "assistant",
                                    "content": [{"type": "text", "text": "BACKLOG_BLOCKER: old marker"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "message",
                                "timestamp": "2026-03-15T01:05:00Z",
                                "message": {
                                    "role": "assistant",
                                    "content": [{"type": "text", "text": "BACKLOG_RESULT: shipped fix"}],
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            sessions_path = sessions_dir / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:discord-clawd:main": {
                            "sessionId": "main-session",
                            "sessionFile": str(session_log),
                            "updatedAt": 1773536639259,
                        }
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(_MOD, "AGENTS_ROOT", agents_root):
                outcome = _MOD._extract_ingest_outcome(
                    "discord-clawd",
                    staged_at=_MOD._parse_iso_timestamp("2026-03-15T01:02:00Z"),
                )

            self.assertEqual(outcome["kind"], "result")
            self.assertEqual(outcome["text"], "shipped fix")
            self.assertEqual(outcome["timestamp"], "2026-03-15T01:05:00Z")

    def test_extracts_result_from_result_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result_path = Path(tmpdir) / "sm-005.json"
            result_path.write_text(
                json.dumps(
                    {
                        "task_id": "sm-005",
                        "kind": "result",
                        "text": "implemented the relational state adapter",
                        "timestamp": "2026-03-15T02:00:00Z",
                    }
                ),
                encoding="utf-8",
            )

            outcome = _MOD._extract_result_file_outcome(
                str(result_path),
                task_id="sm-005",
                staged_at=_MOD._parse_iso_timestamp("2026-03-15T01:59:00Z"),
            )

            self.assertEqual(outcome["kind"], "result")
            self.assertEqual(outcome["text"], "implemented the relational state adapter")

    def test_extracts_repo_acp_error_as_blocker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_root = Path(tmpdir)
            sessions_dir = agents_root / "codex" / "sessions"
            sessions_dir.mkdir(parents=True)
            session_log = sessions_dir / "repo-session.jsonl"
            session_log.write_text(
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-15T02:53:32Z",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "ACP error (ACP_TURN_FAILED): Permission denied by ACP runtime (acpx). ACPX blocked a write/exec permission request in a non-interactive session.\nnext: Retry, or use `/acp cancel` and send the message again.",
                                }
                            ],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            sessions_path = sessions_dir / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:codex:acp:repo-session": {
                            "sessionId": "repo-session",
                            "updatedAt": 1773543212316,
                            "acp": {"agent": "codex", "cwd": str(_MOD.REPO_ROOT), "state": "error"},
                        }
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(_MOD, "AGENTS_ROOT", agents_root):
                outcome = _MOD._extract_repo_acp_error_outcome(
                    "codex",
                    session_key="agent:codex:acp:repo-session",
                    staged_at=_MOD._parse_iso_timestamp("2026-03-15T02:50:00Z"),
                )

            self.assertEqual(outcome["kind"], "blocker")
            self.assertIn("Permission denied by ACP runtime", outcome["text"])


class TestRouting(unittest.TestCase):
    def test_task_prefers_repo_runner_for_known_source_task(self):
        self.assertTrue(
            _MOD._task_prefers_repo_runner(
                {
                    "id": "sm-005",
                    "mission_task_id": "source-005",
                    "title": "Relational State Layer",
                }
            )
        )

    def test_repo_coding_session_route_picks_repo_cwd_acp_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_root = Path(tmpdir)
            sessions_dir = agents_root / "codex" / "sessions"
            sessions_dir.mkdir(parents=True)
            sessions_path = sessions_dir / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:codex:acp:repo-old": {
                            "sessionId": "old",
                            "label": "other",
                            "updatedAt": 5,
                            "acp": {"agent": "codex", "cwd": str(_MOD.REPO_ROOT)},
                        },
                        "agent:codex:acp:repo-preferred": {
                            "sessionId": "preferred",
                            "label": "source-backlog-c_lawd",
                            "updatedAt": 10,
                            "acp": {"agent": "codex", "cwd": str(_MOD.REPO_ROOT)},
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(_MOD, "AGENTS_ROOT", agents_root):
                route = _MOD._repo_coding_session_route("c_lawd")

            self.assertEqual(route["runtime_agent"], "codex")
            self.assertEqual(route["session_key"], "agent:codex:acp:repo-preferred")
            self.assertEqual(route["stage_kind"], "repo_acp")

    def test_repo_coding_session_route_prefers_idle_over_running(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_root = Path(tmpdir)
            sessions_dir = agents_root / "codex" / "sessions"
            sessions_dir.mkdir(parents=True)
            sessions_path = sessions_dir / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:codex:acp:repo-running": {
                            "sessionId": "running-session",
                            "label": "source-backlog-dali",
                            "updatedAt": 20,
                            "acp": {"agent": "codex", "cwd": str(_MOD.REPO_ROOT), "state": "running"},
                        },
                        "agent:codex:acp:repo-idle": {
                            "sessionId": "idle-session",
                            "label": "source-backlog-dali",
                            "updatedAt": 10,
                            "acp": {"agent": "codex", "cwd": str(_MOD.REPO_ROOT), "state": "idle"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (sessions_dir / "idle-session.jsonl").write_text("", encoding="utf-8")

            with patch.object(_MOD, "AGENTS_ROOT", agents_root):
                route = _MOD._repo_coding_session_route("dali")

            self.assertEqual(route["session_key"], "agent:codex:acp:repo-idle")
            self.assertTrue(route["session_file"].endswith("idle-session.jsonl"))

    def test_bypasses_history_suppression_for_repo_reroute(self):
        should_bypass = _MOD._should_bypass_history_suppression(
            {"mission_task_id": "source-005", "title": "Relational State Layer"},
            {
                "kind": "blocker",
                "detail": 'Sandbox blocks source/governance access. Spawn subagent (runtime="acp").',
            },
        )
        self.assertTrue(should_bypass)


class TestTaskStagedTs(unittest.TestCase):
    def test_prefers_started_at(self):
        task = {
            "started_at": "2026-03-15T01:07:33Z",
            "updated_at": "2026-03-15T01:08:00Z",
            "created_at": "2026-03-15T01:00:00Z",
        }
        self.assertEqual(_MOD._task_staged_ts(task, 0.0), _MOD._parse_iso_timestamp("2026-03-15T01:07:33Z"))

    def test_falls_back_to_now_when_task_has_no_timestamps(self):
        self.assertEqual(_MOD._task_staged_ts({}, 123.0), 123.0)


class TestRun(unittest.TestCase):
    def test_run_skips_externally_managed_active_task_without_state_entry(self):
        tasks = [
            {
                "id": "101",
                "origin": "source_mission_config",
                "title": "[Dali] Canonicalize mission state across UI, API, and files",
                "status": "in_progress",
                "priority": "high",
                "assignee": "dali",
                "created_at": "2026-03-16T01:00:00Z",
            }
        ]

        with patch.object(_MOD, "_fetch_tasks", return_value=tasks), patch.object(_MOD, "_write_json"):
            summary = _MOD.run("http://example.test/api/tasks")

        self.assertIn(
            {"assignee": "dali", "runtime_agent": "discord-orchestrator", "reason": "externally-managed-active"},
            summary["skipped"],
        )


if __name__ == "__main__":
    unittest.main()
