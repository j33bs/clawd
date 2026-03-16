import io
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

import app as source_ui_app  # noqa: E402


class TestSourceUIState(unittest.TestCase):
    def test_state_loads_and_persists_command_history(self):
        with tempfile.TemporaryDirectory() as td:
            history_path = Path(td) / "command_history.json"
            history_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "evt-1",
                            "command": "status snapshot",
                            "action": "status_snapshot",
                            "ok": True,
                            "summary": "Captured agent/model snapshot.",
                            "output": "[]",
                            "timestamp": "2026-03-12T00:00:00",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(source_ui_app, "COMMAND_HISTORY_PATH", history_path):
                state = source_ui_app.State()
                self.assertEqual(len(state.command_events), 1)
                state.command_events.insert(
                    0,
                    {
                        "id": "evt-2",
                        "command": "refresh",
                        "action": "refresh",
                        "ok": True,
                        "summary": "Refreshed local Source UI state.",
                        "output": "",
                        "timestamp": "2026-03-12T00:05:00",
                    },
                )
                state.persist_command_events()

            stored = json.loads(history_path.read_text(encoding="utf-8"))
            self.assertEqual(stored[0]["id"], "evt-2")
            self.assertEqual(stored[1]["id"], "evt-1")

    def test_state_loads_and_persists_command_receipts(self):
        with tempfile.TemporaryDirectory() as td:
            receipts_path = Path(td) / "command_receipts.json"
            receipts_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "receipt-1",
                            "command": "restart gateway",
                            "action": "restart_gateway",
                            "status": "pending_approval",
                            "requires_confirmation": True,
                            "summary": "Approval required before executing this command.",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(source_ui_app, "COMMAND_RECEIPTS_PATH", receipts_path):
                state = source_ui_app.State()
                self.assertEqual(len(state.command_receipts), 1)
                self.assertEqual(state.command_receipts[0]["boundary"]["items"][2]["label"], "approval required")
                state.command_receipts.insert(
                    0,
                    {
                        "id": "receipt-2",
                        "command": "status snapshot",
                        "action": "status_snapshot",
                        "status": "completed",
                        "requires_confirmation": False,
                        "summary": "Captured agent/model snapshot.",
                    },
                )
                state.persist_command_receipts()

            stored = json.loads(receipts_path.read_text(encoding="utf-8"))
            self.assertEqual(stored[0]["id"], "receipt-2")
            self.assertEqual(stored[1]["id"], "receipt-1")


class TestSourceUIServing(unittest.TestCase):
    def _make_handler(self, static_dir: Path):
        handler = object.__new__(source_ui_app.SourceUIHandler)
        handler._config = source_ui_app.Config(static_dir=str(static_dir))
        handler.send_response = mock.Mock()
        handler.send_header = mock.Mock()
        handler.end_headers = mock.Mock()
        handler.send_error = mock.Mock()
        handler.wfile = io.BytesIO()
        return handler

    def test_serve_static_disables_cache_for_js(self):
        with tempfile.TemporaryDirectory() as td:
            static_dir = Path(td)
            js_path = static_dir / "js"
            js_path.mkdir(parents=True, exist_ok=True)
            (js_path / "app.js").write_text("console.log('ok');", encoding="utf-8")

            handler = self._make_handler(static_dir)
            handler.serve_static("js/app.js")

            header_calls = [call.args for call in handler.send_header.call_args_list]
            self.assertIn(("Cache-Control", "no-store"), header_calls)
            self.assertEqual(handler.wfile.getvalue(), b"console.log('ok');")

    def test_record_command_event_persists_history(self):
        with tempfile.TemporaryDirectory() as td:
            history_path = Path(td) / "command_history.json"
            with mock.patch.object(source_ui_app, "COMMAND_HISTORY_PATH", history_path):
                state = source_ui_app.State()
                source_ui_app.SourceUIHandler._state = state
                handler = object.__new__(source_ui_app.SourceUIHandler)
                handler._record_command_event(
                    command_text="status snapshot",
                    result={
                        "ok": True,
                        "action": "status_snapshot",
                        "summary": "Captured agent/model snapshot.",
                        "output": "[]",
                    },
                )

            stored = json.loads(history_path.read_text(encoding="utf-8"))
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["action"], "status_snapshot")

    def test_load_agents_prefers_live_openclaw_snapshot(self):
        state = source_ui_app.State()
        source_ui_app.SourceUIHandler._state = state
        handler = object.__new__(source_ui_app.SourceUIHandler)
        with mock.patch.object(
            handler,
            "_run_local_command",
            return_value={
                "ok": True,
                "output": json.dumps(
                    [
                        {
                            "id": "main",
                            "identityName": "Dali",
                            "model": "openai-codex/gpt-5.4",
                            "bindings": 0,
                            "isDefault": True,
                            "workspace": "/home/jeebs/.openclaw/workspace",
                            "routes": ["default (no explicit rules)"],
                        }
                    ]
                ),
            },
        ):
            rows = handler._load_agents()

        self.assertEqual(rows[0]["id"], "main")
        self.assertEqual(rows[0]["name"], "Dali")
        self.assertEqual(rows[0]["status"], "working")

    def test_dispatch_command_requires_confirmation_for_restart_gateway(self):
        with tempfile.TemporaryDirectory() as td:
            receipts_path = Path(td) / "command_receipts.json"
            state = source_ui_app.State()
            source_ui_app.SourceUIHandler._state = state
            handler = object.__new__(source_ui_app.SourceUIHandler)
            with mock.patch.object(source_ui_app, "COMMAND_RECEIPTS_PATH", receipts_path):
                state.command_receipts = []
                result = handler._dispatch_command({"action": "restart_gateway"})

            self.assertFalse(result["ok"])
            self.assertTrue(result["requires_confirmation"])
            self.assertEqual(result["receipt"]["status"], "pending_approval")
            self.assertEqual(result["receipt"]["boundary"]["items"][2]["label"], "approval required")

    def test_dispatch_command_updates_receipt_when_confirmed(self):
        with tempfile.TemporaryDirectory() as td:
            receipts_path = Path(td) / "command_receipts.json"
            state = source_ui_app.State()
            source_ui_app.SourceUIHandler._state = state
            handler = object.__new__(source_ui_app.SourceUIHandler)
            class ImmediateThread:
                def __init__(self, *, target=None, kwargs=None, daemon=None):
                    self._target = target
                    self._kwargs = kwargs or {}

                def start(self):
                    if self._target:
                        self._target(**self._kwargs)

            with (
                mock.patch.object(source_ui_app, "COMMAND_RECEIPTS_PATH", receipts_path),
                mock.patch.object(source_ui_app.threading, "Thread", ImmediateThread),
                mock.patch.object(
                    handler,
                    "_run_local_command",
                    return_value={"ok": True, "output": "restarted"},
                ),
            ):
                state.command_receipts = []
                pending = handler._dispatch_command({"action": "restart_gateway"})
                result = handler._dispatch_command(
                    {
                        "action": "restart_gateway",
                        "receipt_id": pending["receipt"]["id"],
                        "confirmed": True,
                    }
                )

            self.assertTrue(result["ok"])
            self.assertTrue(result["queued"])
            self.assertEqual(result["receipt"]["status"], "queued")
            self.assertFalse(result["receipt"]["requires_confirmation"])
            self.assertEqual(state.command_receipts[0]["status"], "completed")
            self.assertTrue(state.command_receipts[0]["ok"])

    def test_control_agent_persists_operator_intent(self):
        with tempfile.TemporaryDirectory() as td:
            controls_path = Path(td) / "agent_controls.json"
            state = source_ui_app.State()
            source_ui_app.SourceUIHandler._state = state
            handler = object.__new__(source_ui_app.SourceUIHandler)
            handler.send_json = mock.Mock()
            with mock.patch.object(source_ui_app, "AGENT_CONTROLS_PATH", controls_path):
                state.agent_controls = {}
                handler.control_agent("discord-gpt54", "pause")

            stored = json.loads(controls_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["discord-gpt54"]["state"], "paused")
            response = handler.send_json.call_args.args[0]
            self.assertTrue(response["ok"])
            self.assertEqual(response["control_state"], "paused")

    def test_handle_api_returns_display_mode_status(self):
        handler = object.__new__(source_ui_app.SourceUIHandler)
        handler.send_json = mock.Mock()
        parsed = source_ui_app.urlparse("/api/display-mode")
        with mock.patch.object(
            source_ui_app,
            "display_mode_load_status",
            return_value={"ok": True, "profile_current": "fishtank", "toggle_target": "work"},
        ):
            handler.handle_api(parsed)

        response = handler.send_json.call_args.args[0]
        self.assertTrue(response["ok"])
        self.assertEqual(response["profile_current"], "fishtank")

    def test_toggle_display_mode_handler_returns_toggle_payload(self):
        handler = object.__new__(source_ui_app.SourceUIHandler)
        handler.send_json = mock.Mock()
        with mock.patch.object(
            source_ui_app,
            "display_mode_toggle",
            return_value={"ok": True, "profile_current": "work", "toggle_target": "fishtank"},
        ):
            handler.toggle_display_mode_handler()

        response = handler.send_json.call_args.args[0]
        self.assertTrue(response["ok"])
        self.assertEqual(response["profile_current"], "work")

    def test_load_tasks_prefers_aggregated_runtime_plus_local_store(self):
        state = source_ui_app.State()
        source_ui_app.SourceUIHandler._state = state
        handler = object.__new__(source_ui_app.SourceUIHandler)
        expected = [
            {"id": "runtime:dali:codex:abc", "title": "Live session", "read_only": True},
            {"id": 1001, "title": "Local task", "read_only": False},
        ]
        with mock.patch.object(source_ui_app, "task_store_load_all_tasks", return_value=expected):
            rows = handler._load_tasks()

        self.assertEqual(rows, expected)
        self.assertEqual(state.tasks, expected)


if __name__ == "__main__":
    unittest.main()
