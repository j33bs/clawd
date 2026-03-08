"""Tests for intent_failure_scan — redact, find_pattern, _parse_since, _event_timestamp,
scan_router_events, and format_report."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import intent_failure_scan as ifs


class TestRedact(unittest.TestCase):
    """Tests for redact() — secret scrubbing."""

    def test_sk_api_key_redacted(self):
        text = "auth failed: sk-abcdef12345678901234"
        result = ifs.redact(text)
        self.assertNotIn("sk-abcdef12345678901234", result)
        self.assertIn("***", result)

    def test_gsk_key_redacted(self):
        text = "token=gsk_xyzXYZ123456789012345"
        result = ifs.redact(text)
        self.assertNotIn("gsk_xyzXYZ123456789012345", result)
        self.assertIn("***", result)

    def test_short_sk_prefix_not_redacted(self):
        """Keys shorter than 10 chars after prefix are not matched."""
        text = "sk-short"
        result = ifs.redact(text)
        self.assertEqual(result, text)

    def test_normal_text_unchanged(self):
        text = "Connection refused: localhost:8080"
        result = ifs.redact(text)
        self.assertEqual(result, text)

    def test_empty_string_returns_empty(self):
        self.assertEqual(ifs.redact(""), "")

    def test_none_returns_none(self):
        self.assertIsNone(ifs.redact(None))


class TestFindPattern(unittest.TestCase):
    """Tests for find_pattern() — ERROR_PATTERNS matching."""

    def test_429_quota_matches_qwen(self):
        pat = ifs.find_pattern("429 request quota exceeded for this model")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "qwen_quota")

    def test_request_too_large_matches_groq_tpm(self):
        pat = ifs.find_pattern("Request too large for model groq/llama3")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "groq_tpm")

    def test_tpm_matches_groq(self):
        pat = ifs.find_pattern("TPM limit exceeded")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "groq_tpm")

    def test_not_found_error_matches_anthropic(self):
        pat = ifs.find_pattern("not_found_error: model not found in Anthropic API")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "anthropic_404")

    def test_ollama_404_matches(self):
        pat = ifs.find_pattern("404 page not found at localhost:11434")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "ollama_404")

    def test_telegram_not_configured_matches(self):
        pat = ifs.find_pattern("No allowed Telegram chat IDs configured")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "telegram_not_configured")

    def test_chat_not_found_matches_telegram(self):
        pat = ifs.find_pattern("telegram_chat_not_found")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "telegram_chat_not_found")

    def test_chat_not_allowed_matches(self):
        pat = ifs.find_pattern("not in allowlist")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "telegram_chat_not_allowed")

    def test_openclaw_status_unavailable_matches(self):
        pat = ifs.find_pattern("openclaw_status_unavailable command timed out")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "openclaw_status_unavailable")

    def test_unknown_error_returns_none(self):
        pat = ifs.find_pattern("some random unrecognized error message")
        self.assertIsNone(pat)

    def test_pattern_returns_fixes_list(self):
        pat = ifs.find_pattern("429 quota exceeded")
        self.assertIn("fixes", pat)
        self.assertIsInstance(pat["fixes"], list)
        self.assertGreater(len(pat["fixes"]), 0)

    def test_case_insensitive_matching(self):
        pat = ifs.find_pattern("REQUEST TOO LARGE for groq")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "groq_tpm")


class TestParseSince(unittest.TestCase):
    """Tests for _parse_since() — epoch/ISO timestamp parsing."""

    def test_none_returns_none(self):
        self.assertIsNone(ifs._parse_since(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(ifs._parse_since(""))

    def test_whitespace_returns_none(self):
        self.assertIsNone(ifs._parse_since("   "))

    def test_large_epoch_ms_returned_as_is(self):
        # Value > 1e12 → treat as ms
        result = ifs._parse_since("1700000000000")
        self.assertEqual(result, 1700000000000)

    def test_small_epoch_seconds_converted_to_ms(self):
        # Value < 1e12 → treat as seconds, convert to ms
        result = ifs._parse_since("1700000000")
        self.assertEqual(result, 1700000000000)

    def test_iso_string_with_z_parsed(self):
        result = ifs._parse_since("2026-01-01T00:00:00Z")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, int)

    def test_iso_string_without_tz_parsed(self):
        result = ifs._parse_since("2026-01-01T12:00:00")
        self.assertIsNotNone(result)

    def test_garbage_string_returns_none(self):
        result = ifs._parse_since("not-a-timestamp")
        self.assertIsNone(result)


class TestEventTimestamp(unittest.TestCase):
    """Tests for _event_timestamp() — obj timestamp extraction."""

    def test_integer_timestamp_field_used(self):
        obj = {"timestamp": 1700000000000}  # ms
        self.assertEqual(ifs._event_timestamp(obj), 1700000000000)

    def test_float_epoch_seconds_converted(self):
        obj = {"timestamp": 1700000000.0}  # seconds
        self.assertEqual(ifs._event_timestamp(obj), 1700000000000)

    def test_string_iso_timestamp_parsed(self):
        obj = {"timestamp": "2026-01-01T00:00:00Z"}
        result = ifs._event_timestamp(obj)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, int)

    def test_ts_field_fallback(self):
        obj = {"ts": 1700000000000}
        self.assertEqual(ifs._event_timestamp(obj), 1700000000000)

    def test_missing_timestamp_returns_none(self):
        obj = {"event": "something"}
        self.assertIsNone(ifs._event_timestamp(obj))


class TestScanRouterEvents(unittest.TestCase):
    """Tests for scan_router_events()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_events(self, events: list) -> Path:
        path = self._tmp / "router.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
        return path

    def test_missing_file_returns_zero_total(self):
        path = self._tmp / "nonexistent.jsonl"
        result = ifs.scan_router_events(path)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["by_reason"], {})

    def test_counts_router_fail_events(self):
        events = [
            {"event": "router_fail", "detail": {"reason_code": "request_http_429"}},
            {"event": "router_fail", "detail": {"reason_code": "request_http_429"}},
        ]
        result = ifs.scan_router_events(self._write_events(events))
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["by_reason"]["request_http_429"], 2)

    def test_counts_router_escalate_events(self):
        events = [
            {"event": "router_escalate", "detail": {"reason_code": "request_timeout"}},
        ]
        result = ifs.scan_router_events(self._write_events(events))
        self.assertEqual(result["total"], 1)

    def test_ignores_non_fail_events(self):
        events = [
            {"event": "router_success", "detail": {"reason_code": "ok"}},
            {"event": "router_skip", "detail": {"reason_code": "auth_login_required"}},
        ]
        result = ifs.scan_router_events(self._write_events(events))
        self.assertEqual(result["total"], 0)

    def test_ignores_events_with_no_reason_code(self):
        events = [
            {"event": "router_fail", "detail": {}},
        ]
        result = ifs.scan_router_events(self._write_events(events))
        self.assertEqual(result["total"], 0)

    def test_mixed_reasons_aggregated(self):
        events = [
            {"event": "router_fail", "detail": {"reason_code": "request_http_429"}},
            {"event": "router_escalate", "detail": {"reason_code": "request_timeout"}},
            {"event": "router_fail", "detail": {"reason_code": "request_http_429"}},
        ]
        result = ifs.scan_router_events(self._write_events(events))
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["by_reason"]["request_http_429"], 2)
        self.assertEqual(result["by_reason"]["request_timeout"], 1)

    def test_invalid_json_lines_skipped(self):
        path = self._tmp / "bad.jsonl"
        path.write_text(
            'not json\n{"event":"router_fail","detail":{"reason_code":"timeout"}}\n',
            encoding="utf-8",
        )
        result = ifs.scan_router_events(path)
        self.assertEqual(result["total"], 1)


class TestFormatReport(unittest.TestCase):
    """Tests for format_report() — markdown report structure."""

    def test_empty_findings_contains_no_errors_message(self):
        report = ifs.format_report([])
        self.assertIn("No errors found", report)

    def test_report_has_header(self):
        report = ifs.format_report([])
        self.assertIn("Intent Failure Report", report)

    def test_total_errors_in_summary(self):
        finding = {
            "timestamp": None,
            "file": "test.jsonl",
            "error": "429 quota exceeded for model",
            "pattern": ifs.find_pattern("429 quota exceeded"),
        }
        report = ifs.format_report([finding])
        self.assertIn("total_errors: 1", report)

    def test_findings_show_intent(self):
        finding = {
            "timestamp": None,
            "file": "test.jsonl",
            "error": "429 request quota exceeded",
            "pattern": ifs.find_pattern("429 request quota exceeded"),
        }
        report = ifs.format_report([finding])
        self.assertIn("Intent:", report)
        self.assertIn("LLM response (Qwen Portal)", report)

    def test_unknown_pattern_shows_unknown_intent(self):
        finding = {
            "timestamp": None,
            "file": "test.jsonl",
            "error": "some unknown error",
            "pattern": None,
        }
        report = ifs.format_report([finding])
        self.assertIn("Unknown intent", report)


if __name__ == "__main__":
    unittest.main()
