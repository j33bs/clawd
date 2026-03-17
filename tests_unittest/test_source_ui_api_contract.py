import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
MODULE_PATH = SOURCE_UI_ROOT / "app.py"

if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

SPEC = importlib.util.spec_from_file_location("_source_ui_app_contract", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules["_source_ui_app_contract"] = MOD
SPEC.loader.exec_module(MOD)


class SourceUIApiContractTests(unittest.TestCase):
    def _make_handler(self):
        handler = object.__new__(MOD.SourceUIHandler)
        handler._config = MOD.Config(static_dir=str(SOURCE_UI_ROOT / "static"))
        handler._state = MOD.State()
        handler.send_json = mock.Mock()
        return handler

    def test_load_source_mission_accepts_plain_config_payload(self):
        with tempfile.TemporaryDirectory() as td:
            mission_path = Path(td) / "source_mission.json"
            runtime_path = Path(td) / "source_runtime_state.json"
            mission_path.write_text(
                json.dumps(
                    {
                        "statement": "Build a better Source UI.",
                        "tasks": [{"id": "source-001", "title": "Universal Context Packet"}],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            with (
                mock.patch.object(MOD, "SOURCE_MISSION_PATH", mission_path),
                mock.patch.object(MOD, "SOURCE_RUNTIME_STATE_PATH", runtime_path),
            ):
                mission = MOD.DemoDataGenerator.load_source_mission()

        self.assertIsInstance(mission, dict)
        self.assertEqual(mission["statement"], "Build a better Source UI.")
        self.assertEqual(mission["tasks"][0]["id"], "source-001")

    def test_hydrate_task_metadata_does_not_double_prefix_source_ids(self):
        task, changed = MOD.DemoDataGenerator.hydrate_task_metadata(
            {"id": "source-001", "title": "Universal Context Packet"},
            index=0,
        )

        self.assertTrue(changed)
        self.assertEqual(task["mission_task_id"], "source-001")

    def test_status_endpoint_merges_tacti_status_data(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(
                MOD,
                "portfolio_payload",
                return_value={
                    "runtime_agents": [{"id": "session:main", "name": "c_lawd", "status": "working"}],
                    "scheduled_jobs": [
                        {
                            "id": "cron-1",
                            "name": "Hourly Check",
                            "cron": "0 * * * *",
                            "enabled": True,
                            "last_run_at": "2026-03-17T05:03:01.206000Z",
                            "next_run_at": "2026-03-17T06:03:01.197000Z",
                            "last_status": "ok",
                        }
                    ],
                    "activity_logs": [{"level": "info", "message": "live log"}],
                    "components": [{"id": "gateway", "status": "healthy"}],
                    "health_metrics": {"cpu": 12, "memory": 34, "disk": 56, "gpu": 0},
                    "gateway_connected": True,
                    "memory_ops": {
                        "status": "active",
                        "summary": "42 total memory rows | 3 active inferences",
                        "totals": {"rows": 42, "inferences": 3},
                        "sources": [
                            {"label": "Telegram Main", "updated_at": "2026-03-17T01:32:07.476735Z"},
                        ],
                        "preference_profile": {
                            "top_prompt_lines": ["Prefer concise operational summaries."]
                        },
                    },
                },
            ),
            mock.patch.object(
                MOD,
                "get_status_data",
                return_value={
                    "memory": {"process_rss_mb": 12.5},
                    "cron": {"status": "ok"},
                    "knowledge_base_sync": {"status": "stale"},
                },
            ),
            mock.patch.object(
                MOD,
                "load_task_store_tasks",
                return_value=[
                    {"id": 1001, "title": "Live task", "status": "backlog", "origin": "dashboard"},
                    {"id": 1002, "title": "Review task", "status": "review", "origin": "dashboard"},
                    {"id": "sm-001", "title": "Mission task", "status": "backlog", "origin": "source_mission_config"},
                ],
            ),
        ):
            handler.handle_api(MOD.urlparse("/api/status"))

        payload = handler.send_json.call_args.args[0]
        self.assertIn("agents", payload)
        self.assertIn("truth", payload)
        self.assertEqual(payload["memory"]["process_rss_mb"], 12.5)
        self.assertEqual(payload["cron"]["status"], "ok")
        self.assertEqual(payload["agents"][0]["id"], "session:main")
        self.assertEqual(payload["scheduled_jobs"][0]["id"], "cron-1")
        self.assertEqual(payload["logs"][0]["message"], "live log")
        self.assertEqual(payload["components"][0]["id"], "gateway")
        self.assertEqual(payload["health_metrics"]["cpu"], 12)
        self.assertTrue(payload["gateway_connected"])
        self.assertEqual(payload["memory_system"]["total_rows"], 42)
        self.assertEqual(payload["memory_system"]["active_inferences"], 3)
        self.assertEqual(payload["memory_system"]["latest_source_label"], "Telegram Main")
        self.assertNotIn("knowledge_base_sync", payload)
        self.assertEqual(payload["cron"]["status"], "ok")
        self.assertEqual(payload["cron"]["enabled_jobs"], 1)
        self.assertEqual(payload["tasks_total"], 2)
        self.assertEqual(payload["task_counts"]["backlog"], 1)
        self.assertEqual(payload["task_counts"]["review"], 1)
        self.assertEqual(len(payload["tasks"]), 2)
        self.assertTrue(all(str(task.get("origin")) != "source_mission_config" for task in payload["tasks"]))

    def test_tasks_endpoint_uses_canonical_task_store(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(
                MOD,
                "load_task_store_tasks",
                return_value=[
                    {"id": 1001, "title": "Live task", "status": "backlog", "origin": "dashboard"},
                    {"id": "sm-001", "title": "Mission task", "status": "backlog", "origin": "source_mission_config"},
                ],
            ),
        ):
            handler.handle_api(MOD.urlparse("/api/tasks"))

        payload = handler.send_json.call_args.args[0]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], 1001)

    def test_agents_endpoint_uses_runtime_agents(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(MOD, "portfolio_payload", return_value={"runtime_agents": [{"id": "session:main", "name": "c_lawd"}]}),
        ):
            handler.handle_api(MOD.urlparse("/api/agents"))

        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload[0]["id"], "session:main")

    def test_schedule_endpoint_uses_runtime_schedules(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(MOD, "portfolio_payload", return_value={"scheduled_jobs": [{"id": "cron-1", "name": "Hourly"}]}),
        ):
            handler.handle_api(MOD.urlparse("/api/schedule"))

        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload[0]["id"], "cron-1")

    def test_logs_endpoint_uses_runtime_activity_logs(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(MOD, "portfolio_payload", return_value={"activity_logs": [{"level": "info", "message": "live log"}]}),
        ):
            handler.handle_api(MOD.urlparse("/api/logs"))

        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload[0]["message"], "live log")

    def test_oracle_endpoint_uses_runtime_query_helper(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(
                MOD,
                "_run_oracle_query",
                return_value={"question": "What does the record say?", "results": [{"body": "answer"}]},
            ) as oracle_query,
        ):
            handler.handle_api(MOD.urlparse("/api/oracle?q=What%20does%20the%20record%20say%3F&k=7"))

        oracle_query.assert_called_once_with("What does the record say?", k=7, being=None)
        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload["question"], "What does the record say?")

    def test_oracle_endpoint_can_attach_answer_payload(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(
                MOD,
                "_run_oracle_query",
                return_value={"question": "What does the record say?", "results": [{"body": "answer"}]},
            ) as oracle_query,
            mock.patch.object(
                MOD,
                "_augment_oracle_payload_with_answer",
                return_value={"question": "What does the record say?", "results": [{"body": "answer"}], "answer": "Grounded."},
            ) as augment,
        ):
            handler.handle_api(MOD.urlparse("/api/oracle?q=What%20does%20the%20record%20say%3F&k=7&answer=1"))

        oracle_query.assert_called_once_with("What does the record say?", k=7, being=None)
        augment.assert_called_once()
        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload["answer"], "Grounded.")

    def test_oracle_post_defaults_to_plain_text_answer(self):
        handler = self._make_handler()
        handler._read_json_body = mock.Mock(return_value={"q": "What does the record say?", "k": 5})
        with (
            mock.patch.object(
                MOD,
                "_run_oracle_query",
                return_value={"question": "What does the record say?", "results": [{"body": "answer"}]},
            ) as oracle_query,
            mock.patch.object(
                MOD,
                "_augment_oracle_payload_with_answer",
                return_value={"question": "What does the record say?", "results": [{"body": "answer"}], "answer": "Grounded."},
            ) as augment,
        ):
            handler.query_oracle_handler()

        oracle_query.assert_called_once_with("What does the record say?", k=5, being=None)
        augment.assert_called_once_with("What does the record say?", {"question": "What does the record say?", "results": [{"body": "answer"}]})
        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload["answer"], "Grounded.")

    def test_augment_oracle_payload_with_answer_falls_back_deterministically(self):
        base_payload = {
            "question": "Where is the plan?",
            "results": [{"title": "Plan", "body": "The plan is in workspace/docs/MASTER_PLAN.md", "location": "/tmp/MASTER_PLAN.md"}],
            "locations": [{"kind": "project_file", "label": "MASTER_PLAN.md", "location": "/tmp/MASTER_PLAN.md"}],
        }
        with mock.patch.object(MOD, "_query_local_oracle_answer", side_effect=RuntimeError("local lane unavailable")):
            payload = MOD._augment_oracle_payload_with_answer("Where is the plan?", base_payload)

        self.assertEqual(payload["answer_mode"], "deterministic_fallback")
        self.assertIn("Sources:", payload["answer"])
        self.assertEqual(payload["answer_error"], "local lane unavailable")

    def test_fallback_oracle_query_reads_broader_system_corpus(self):
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            open_questions_path = temp_root / "OPEN_QUESTIONS.md"
            graph_path = temp_root / "graph.jsonl"
            research_import_path = temp_root / "research_import.jsonl"
            research_papers_path = temp_root / "papers.jsonl"
            research_doc_root = temp_root / "research"
            user_inferences_path = temp_root / "user_inferences.jsonl"
            preference_profile_path = temp_root / "preference_profile.json"
            system_status_path = temp_root / "SYSTEM_STATUS.md"
            research_doc_root.mkdir(parents=True, exist_ok=True)

            open_questions_path.write_text(
                "# OPEN_QUESTIONS.md\n\n## I. Consciousness Notes (2026-03-17)\nThe correspondence discusses identity and continuity.\n",
                encoding="utf-8",
            )
            graph_path.write_text(
                json.dumps(
                    {
                        "name": "Runtime orchestration",
                        "content": "The wider system routes live agents, dashboards, and schedulers together.",
                        "source": "workspace/knowledge_base/data/graph.jsonl",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            research_import_path.write_text("", encoding="utf-8")
            research_papers_path.write_text("", encoding="utf-8")
            user_inferences_path.write_text(
                json.dumps(
                    {
                        "subject": "jeebs",
                        "status": "active",
                        "statement": "Prefers concise operational summaries.",
                        "prompt_line": "Prefer concise, direct operational responses by default.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            preference_profile_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "subject": "jeebs",
                        "updated_at": "2026-03-17T01:00:00Z",
                        "communication": {
                            "concise_default": {
                                "value": True,
                                "statement": "Prefers concise operational summaries.",
                                "prompt_line": "Prefer concise, direct operational responses by default.",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            system_status_path.write_text(
                "# System Status\n\nThe system dashboard reflects current runtime orchestration.\n",
                encoding="utf-8",
            )

            with (
                mock.patch.object(MOD.oracle_corpus, "ORACLE_CORRESPONDENCE_PATH", open_questions_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_GRAPH_PATH", graph_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_RESEARCH_IMPORT_PATH", research_import_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_RESEARCH_PAPERS_PATH", research_papers_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_RESEARCH_DOC_ROOT", research_doc_root),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_USER_INFERENCES_PATH", user_inferences_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_PREFERENCE_PROFILE_PATH", preference_profile_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_MEMORY_SOURCES", ()),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_CORE_DOC_PATHS", (system_status_path,)),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_PROJECT_INDEX_ROOTS", ()),
            ):
                MOD.oracle_corpus.invalidate_corpus_cache()
                payload = MOD._fallback_oracle_query("runtime orchestration", k=5)

        self.assertEqual(payload["source"], "system_corpus")
        self.assertTrue(payload["results"])
        self.assertTrue(any("Knowledge Graph" in str(row.get("source_label")) for row in payload["results"]))

    def test_fallback_oracle_query_prioritizes_research_hits_for_psychological_queries(self):
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            open_questions_path = temp_root / "OPEN_QUESTIONS.md"
            graph_path = temp_root / "graph.jsonl"
            research_import_path = temp_root / "research_import.jsonl"
            research_papers_path = temp_root / "papers.jsonl"
            research_doc_root = temp_root / "research"
            user_inferences_path = temp_root / "user_inferences.jsonl"
            preference_profile_path = temp_root / "preference_profile.json"
            research_doc_root.mkdir(parents=True, exist_ok=True)

            open_questions_path.write_text(
                "# OPEN_QUESTIONS.md\n\n## I. Being Notes (2026-03-17)\nThe ledger talks about being and continuity.\n",
                encoding="utf-8",
            )
            graph_path.write_text("", encoding="utf-8")
            research_import_path.write_text("", encoding="utf-8")
            research_papers_path.write_text(
                json.dumps(
                    {
                        "title": "Contemporary psychological wellbeing practice",
                        "topic": "therapy",
                        "content": "Cross-disciplinary research on psychological wellbeing, counselling, psychiatry, and therapeutic practice.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            user_inferences_path.write_text("", encoding="utf-8")
            preference_profile_path.write_text(
                json.dumps({"schema_version": 1, "subject": "jeebs", "updated_at": "2026-03-17T01:00:00Z"}),
                encoding="utf-8",
            )

            with (
                mock.patch.object(MOD.oracle_corpus, "ORACLE_CORRESPONDENCE_PATH", open_questions_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_GRAPH_PATH", graph_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_RESEARCH_IMPORT_PATH", research_import_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_RESEARCH_PAPERS_PATH", research_papers_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_RESEARCH_DOC_ROOT", research_doc_root),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_USER_INFERENCES_PATH", user_inferences_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_PREFERENCE_PROFILE_PATH", preference_profile_path),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_MEMORY_SOURCES", ()),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_CORE_DOC_PATHS", ()),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_PROJECT_INDEX_ROOTS", ()),
            ):
                MOD.oracle_corpus.invalidate_corpus_cache()
                payload = MOD._fallback_oracle_query("psychological well being", k=3)

        self.assertTrue(payload["results"])
        self.assertEqual(payload["results"][0]["corpus_kind"], "research_papers")

    def test_fallback_oracle_query_surfaces_project_file_locations(self):
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            project_root = temp_root / "project"
            plans_dir = project_root / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            plan_path = plans_dir / "implemented_plan.md"
            plan_path.write_text(
                "# Implemented Plan\n\nThis plan records implemented task handoffs and file locations.\n",
                encoding="utf-8",
            )

            with (
                mock.patch.object(MOD.oracle_corpus, "ORACLE_CORRESPONDENCE_PATH", temp_root / "missing_oq.md"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_GRAPH_PATH", temp_root / "missing_graph.jsonl"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_RESEARCH_IMPORT_PATH", temp_root / "missing_research_import.jsonl"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_RESEARCH_PAPERS_PATH", temp_root / "missing_papers.jsonl"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_USER_INFERENCES_PATH", temp_root / "missing_user_inferences.jsonl"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_PREFERENCE_PROFILE_PATH", temp_root / "missing_profile.json"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_MEMORY_SOURCES", ()),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_CORE_DOC_PATHS", ()),
                mock.patch.object(
                    MOD.oracle_corpus,
                    "ORACLE_PROJECT_INDEX_ROOTS",
                    (("Project Plans", project_root, {".md"}, 20),),
                ),
            ):
                MOD.oracle_corpus.invalidate_corpus_cache()
                payload = MOD._fallback_oracle_query("implemented plan file locations", k=5)

        self.assertTrue(payload["results"])
        self.assertEqual(payload["results"][0]["corpus_kind"], "project_file")
        self.assertEqual(payload["results"][0]["location"], str(plan_path))
        self.assertTrue(any(row.get("location") == str(plan_path) for row in payload["results"]))
        self.assertTrue(any(location.get("location") == str(plan_path) for location in payload["locations"]))

    def test_fallback_oracle_query_prefers_exact_memory_date_file(self):
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            memory_root = temp_root / "memory"
            memory_root.mkdir(parents=True, exist_ok=True)
            target_path = memory_root / "2026-03-17.md"
            target_path.write_text(
                "Daily notes for 2026-03-17 with memory context.\n",
                encoding="utf-8",
            )
            (memory_root / "2026-03-16.md").write_text(
                "Daily notes for 2026-03-16.\n",
                encoding="utf-8",
            )

            with (
                mock.patch.object(MOD.oracle_corpus, "ORACLE_CORRESPONDENCE_PATH", temp_root / "missing_oq.md"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_GRAPH_PATH", temp_root / "missing_graph.jsonl"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_RESEARCH_IMPORT_PATH", temp_root / "missing_research_import.jsonl"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_RESEARCH_PAPERS_PATH", temp_root / "missing_papers.jsonl"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_USER_INFERENCES_PATH", temp_root / "missing_user_inferences.jsonl"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_PREFERENCE_PROFILE_PATH", temp_root / "missing_profile.json"),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_MEMORY_SOURCES", ()),
                mock.patch.object(MOD.oracle_corpus, "ORACLE_CORE_DOC_PATHS", ()),
                mock.patch.object(
                    MOD.oracle_corpus,
                    "ORACLE_PROJECT_INDEX_ROOTS",
                    (("Daily Memory", memory_root, {".md"}, 20),),
                ),
            ):
                MOD.oracle_corpus.invalidate_corpus_cache()
                payload = MOD._fallback_oracle_query("2026-03-17 memory notes", k=5)

        self.assertTrue(payload["results"])
        self.assertEqual(payload["results"][0]["corpus_kind"], "project_file")
        self.assertEqual(payload["results"][0]["location"], str(target_path))

    def test_create_schedule_endpoint_calls_runtime_creator(self):
        handler = self._make_handler()
        handler._read_json_body = mock.Mock(return_value={"name": "Nightly"})

        with mock.patch.object(MOD, "_create_schedule_job", return_value={"success": True, "id": "cron-1"}) as creator:
            handler.create_schedule()

        creator.assert_called_once_with({"name": "Nightly"})
        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload["id"], "cron-1")

    def test_control_agent_endpoint_calls_runtime_action(self):
        handler = self._make_handler()

        with mock.patch.object(MOD, "_control_runtime_agent_action", return_value={"success": True, "summary": "Stopped"}) as control:
            handler.control_agent("service:dali-fishtank.service", "stop")

        control.assert_called_once_with("service:dali-fishtank.service", "stop")
        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload["summary"], "Stopped")

    def test_persist_source_mission_writes_runtime_state_not_config(self):
        with tempfile.TemporaryDirectory() as td:
            mission_path = Path(td) / "source_mission.json"
            runtime_path = Path(td) / "source_runtime_state.json"
            mission_path.write_text(
                json.dumps(
                    {
                        "statement": "Build a better Source UI.",
                        "tasks": [
                            {
                                "id": "source-001",
                                "title": "Universal Context Packet",
                                "definition_of_done": "Keep all surfaces aligned.",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            handler = self._make_handler()
            handler._state.tasks = [
                {
                    "id": "source-001",
                    "title": "Universal Context Packet",
                    "definition_of_done": "Keep all surfaces aligned.",
                    "status": "in_progress",
                    "progress": 65,
                    "origin": "source_mission_config",
                    "mission_task_id": "source-001",
                    "status_reason": "Active lane work in progress.",
                }
            ]
            handler._state.notifications = [{"id": 1, "title": "Task started"}]
            handler._state.handoffs = []
            handler._state.logs = [{"level": "info", "message": "Task started"}]

            with (
                mock.patch.object(MOD, "SOURCE_MISSION_PATH", mission_path),
                mock.patch.object(MOD, "SOURCE_RUNTIME_STATE_PATH", runtime_path),
            ):
                handler.persist_source_mission()
                merged = MOD.DemoDataGenerator.load_source_mission()

            config_payload = json.loads(mission_path.read_text(encoding="utf-8"))
            runtime_payload = json.loads(runtime_path.read_text(encoding="utf-8"))

            self.assertNotIn("updated_at", config_payload)
            self.assertNotIn("notifications", config_payload)
            self.assertNotIn("origin", config_payload["tasks"][0])
            self.assertEqual(runtime_payload["task_overrides"][0]["status"], "in_progress")
            self.assertEqual(runtime_payload["notifications"][0]["title"], "Task started")
            self.assertEqual(merged["tasks"][0]["progress"], 65)
            self.assertEqual(merged["notifications"][0]["title"], "Task started")

    def test_tacti_dream_endpoint_returns_live_payload(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(MOD, "get_dream_status", return_value={"status": "ready", "report_count": 3}),
        ):
            handler.handle_api(MOD.urlparse("/api/tacti/dream"))

        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["report_count"], 3)

    def test_ain_status_payload_uses_phi_proxy(self):
        handler = self._make_handler()
        with mock.patch.object(handler, "_ain_phi_payload", return_value={"phi": 0.9405, "proxy_method": "embedding_coherence"}):
            payload = handler._ain_status_payload()

        self.assertTrue(payload["running"])
        self.assertEqual(payload["state"], "online")
        self.assertAlmostEqual(payload["total_drive"], 0.9405)


if __name__ == "__main__":
    unittest.main()
