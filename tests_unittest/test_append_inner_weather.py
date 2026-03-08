"""Tests for append_inner_weather._sanitize() and append_inner_weather()."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import append_inner_weather as aiw  # noqa: E402


class TestSanitize(unittest.TestCase):
    """Unit tests for _sanitize() — PII scrubbing."""

    def test_email_redacted(self):
        result = aiw._sanitize("Contact user@example.com for details")
        self.assertNotIn("user@example.com", result)
        self.assertIn("[REDACTED_EMAIL]", result)

    def test_long_token_redacted(self):
        token = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWX"
        result = aiw._sanitize(f"Using token {token} here")
        self.assertNotIn(token, result)
        self.assertIn("[REDACTED_TOKEN]", result)

    def test_short_strings_preserved(self):
        result = aiw._sanitize("Normal text without secrets")
        self.assertEqual(result, "Normal text without secrets")

    def test_whitespace_normalized(self):
        result = aiw._sanitize("  extra   whitespace   here  ")
        self.assertEqual(result, "extra whitespace here")

    def test_multiple_emails_all_redacted(self):
        result = aiw._sanitize("From a@b.com to c@d.org")
        self.assertNotIn("a@b.com", result)
        self.assertNotIn("c@d.org", result)
        self.assertEqual(result.count("[REDACTED_EMAIL]"), 2)

    def test_23_char_token_preserved(self):
        """Tokens shorter than 24 chars are NOT redacted."""
        short = "ABC123DEF456GHI789JK012"  # 23 chars
        result = aiw._sanitize(f"token {short} here")
        self.assertIn(short, result)


class TestAppendInnerWeather(unittest.TestCase):
    """Tests for append_inner_weather() file write behaviour."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        # Patch REPO_ROOT so relative path computation works
        self._orig_root = aiw.REPO_ROOT
        aiw.REPO_ROOT = self._tmp

    def tearDown(self):
        aiw.REPO_ROOT = self._orig_root
        self._tmpdir.cleanup()

    def _weather_path(self) -> Path:
        return self._tmp / "weather.md"

    def test_creates_file_if_missing(self):
        path = self._weather_path()
        self.assertFalse(path.exists())
        aiw.append_inner_weather("a note", "TestNode", path)
        self.assertTrue(path.exists())

    def test_appended_content_contains_note(self):
        path = self._weather_path()
        aiw.append_inner_weather("noticing the system", "Dali", path)
        content = path.read_text(encoding="utf-8")
        self.assertIn("noticing the system", content)

    def test_appended_content_contains_node(self):
        path = self._weather_path()
        aiw.append_inner_weather("a note", "c_lawd", path)
        content = path.read_text(encoding="utf-8")
        self.assertIn("[c_lawd]", content)

    def test_multiple_appends_grow_file(self):
        path = self._weather_path()
        aiw.append_inner_weather("first note", "A", path)
        size1 = path.stat().st_size
        aiw.append_inner_weather("second note", "B", path)
        size2 = path.stat().st_size
        self.assertGreater(size2, size1)

    def test_return_value_has_expected_keys(self):
        path = self._weather_path()
        result = aiw.append_inner_weather("a note", "TestNode", path)
        self.assertEqual(result["status"], "appended")
        self.assertIn("timestamp", result)
        self.assertIn("path", result)
        self.assertEqual(result["node"], "TestNode")

    def test_timestamp_format_is_utc_iso(self):
        path = self._weather_path()
        result = aiw.append_inner_weather("a note", "X", path)
        ts = result["timestamp"]
        self.assertTrue(ts.endswith("Z"), f"Expected Z suffix, got: {ts}")
        self.assertEqual(len(ts), 20, f"Expected YYYYMMDDThhmmssZ (20 chars), got: {ts}")

    def test_pii_in_note_is_sanitized_before_write(self):
        path = self._weather_path()
        aiw.append_inner_weather("secret@corp.com token here", "X", path)
        content = path.read_text(encoding="utf-8")
        self.assertNotIn("secret@corp.com", content)
        self.assertIn("[REDACTED_EMAIL]", content)

    def test_parent_dirs_created(self):
        nested = self._tmp / "deep" / "nested" / "weather.md"
        aiw.append_inner_weather("note", "X", nested)
        self.assertTrue(nested.exists())


if __name__ == "__main__":
    unittest.main()
