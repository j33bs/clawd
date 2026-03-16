import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import team_chat_adapters as _tca
from team_chat_adapters import RouterLLMClient, _detect_pause_stuck  # noqa: E402


class _FakeRouter:
    def __init__(self, text: str, parsed=None):
        self._text = text
        self._parsed = parsed

    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        parsed = self._parsed
        if parsed is None and callable(validate_fn):
            parsed = validate_fn(self._text)
        return {"ok": True, "provider": "fake", "model": "fake/model", "reason_code": "ok", "text": self._text, "parsed": parsed}

    def explain_route(self, intent, context_metadata=None, payload=None):
        return {"intent": intent, "mode": "test"}


class TestTeamChatPauseGate(unittest.TestCase):
    def setUp(self):
        # Isolate pause log so the STUCK override doesn't fire from real log state
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_log_path = _tca._PAUSE_LOG_PATH
        _tca._PAUSE_LOG_PATH = Path(self._tmpdir.name) / "pause_check_log.jsonl"

    def tearDown(self):
        _tca._PAUSE_LOG_PATH = self._orig_log_path
        self._tmpdir.cleanup()

    def _make_client(self, text: str):
        client = RouterLLMClient.__new__(RouterLLMClient)
        client.repo_root = REPO_ROOT
        client.router = _FakeRouter(text=text)
        return client

    def test_response_path_unchanged_when_flag_off(self):
        os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
        client = self._make_client('{"plan": {"summary":"s", "risk_level":"low"}, "work_orders": [{"id":"1","title":"t","goal":"g"}]}')

        out = client.run_json(
            intent="coding",
            input_text="task",
            trigger_phrase="use chatgpt",
            prompt="prompt",
            max_tokens=100,
            validate_fn=lambda t: __import__("json").loads(t),
        )
        self.assertTrue(out.ok)
        self.assertEqual(out.data["plan"]["risk_level"], "low")
        self.assertFalse(out.route["pause_check"]["enabled"])

    def test_response_path_pauses_when_enabled_and_filler(self):
        os.environ["OPENCLAW_PAUSE_CHECK"] = "1"
        os.environ["OPENCLAW_PAUSE_CHECK_TEST_MODE"] = "1"
        try:
            filler = "Great question. Let's dive in. Generally speaking, it depends. " * 6
            client = self._make_client(filler)
            out = client.run_json(
                intent="coding",
                input_text="ok",
                trigger_phrase="use chatgpt",
                prompt="prompt",
                max_tokens=100,
                validate_fn=lambda t: None,
            )
            self.assertFalse(out.ok)
            self.assertEqual(out.error, "paused_no_value_add")
            self.assertEqual(out.route["pause_check"]["decision"], "silence")
        finally:
            os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
            os.environ.pop("OPENCLAW_PAUSE_CHECK_TEST_MODE", None)


class TestDetectPauseStuck(unittest.TestCase):
    """Unit tests for _detect_pause_stuck() helper."""

    _STUCK_ENTRY = {
        "decision": "silence",
        "rationale": "verbose",
        "signals": {"fills_space": 0.85, "value_add": 0.0, "silence_ok": 0.85},
    }
    _VARYING_ENTRY = {
        "decision": "proceed",
        "rationale": "concrete",
        "signals": {"fills_space": 0.2, "value_add": 0.6, "silence_ok": 0.1},
    }

    def _write_log(self, path: Path, entries: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_missing_log_returns_false(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(_detect_pause_stuck(Path(td) / "nonexistent.jsonl"))

    def test_too_few_entries_returns_false(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            self._write_log(p, [self._STUCK_ENTRY] * 3)
            self.assertFalse(_detect_pause_stuck(p, threshold=4))

    def test_exactly_threshold_identical_returns_true(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            self._write_log(p, [self._STUCK_ENTRY] * 4)
            self.assertTrue(_detect_pause_stuck(p, threshold=4))

    def test_varied_entries_returns_false(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            entries = [self._STUCK_ENTRY] * 3 + [self._VARYING_ENTRY]
            self._write_log(p, entries)
            self.assertFalse(_detect_pause_stuck(p, threshold=4))

    def test_stuck_at_tail_only_counts_last_n(self):
        """If the tail N entries are stuck but earlier ones vary, still STUCK."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            entries = [self._VARYING_ENTRY] * 3 + [self._STUCK_ENTRY] * 4
            self._write_log(p, entries)
            self.assertTrue(_detect_pause_stuck(p, threshold=4))

    def test_empty_file_returns_false(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            p.write_text("", encoding="utf-8")
            self.assertFalse(_detect_pause_stuck(p, threshold=4))

    def test_malformed_json_returns_false(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            with p.open("w") as f:
                for _ in range(4):
                    f.write("not-valid-json\n")
            self.assertFalse(_detect_pause_stuck(p, threshold=4))


class TestPauseGateStuckOverride(unittest.TestCase):
    """Integration test: STUCK override forces 'proceed' after N identical silence decisions."""

    _STUCK_ENTRY = {
        "decision": "silence",
        "rationale": "draft appears verbose/low-specificity for user signal",
        "signals": {"fills_space": 0.85, "value_add": 0.0, "silence_ok": 0.85},
    }

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_log_path = _tca._PAUSE_LOG_PATH

    def tearDown(self):
        _tca._PAUSE_LOG_PATH = self._orig_log_path
        self._tmpdir.cleanup()

    def _make_log(self, entries: list) -> Path:
        p = Path(self._tmpdir.name) / "pause_check_log.jsonl"
        with p.open("w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        _tca._PAUSE_LOG_PATH = p
        return p

    def test_stuck_override_forces_proceed_after_n_silences(self):
        """After _PAUSE_STUCK_THRESHOLD identical silence decisions in log, next call must proceed."""
        from team_chat_adapters import _PAUSE_STUCK_THRESHOLD

        log_path = self._make_log([self._STUCK_ENTRY] * _PAUSE_STUCK_THRESHOLD)
        # Verify the condition is detected
        self.assertTrue(_detect_pause_stuck(log_path, threshold=_PAUSE_STUCK_THRESHOLD))

    def test_pause_gate_overrides_silence_when_stuck(self):
        """End-to-end: _pause_gate_text returns draft (not sentinel) when STUCK log exists."""
        from team_chat_adapters import _pause_gate_text, _PAUSE_STUCK_THRESHOLD

        self._make_log([self._STUCK_ENTRY] * _PAUSE_STUCK_THRESHOLD)

        os.environ["OPENCLAW_PAUSE_CHECK"] = "1"
        os.environ["OPENCLAW_PAUSE_CHECK_TEST_MODE"] = "1"
        try:
            filler = "Great question. Let's dive in. Generally speaking, it depends. " * 6
            text_out, decision = _pause_gate_text("coding", "ok", filler)
            # The pause classifier would say "silence" but STUCK override should fire
            self.assertEqual(decision.get("decision"), "proceed")
            self.assertTrue(decision.get("stuck_override"))
            self.assertNotEqual(text_out, "(pausing — no value to add)")
        finally:
            os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
            os.environ.pop("OPENCLAW_PAUSE_CHECK_TEST_MODE", None)


if __name__ == "__main__":
    unittest.main()
