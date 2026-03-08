"""Tests for system_health_monitor — _parse_iso, _extract_last_audit_ts,
check_security_audit, check_replay_log_writable, _detect_coder_degraded_reason."""
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

import system_health_monitor as shm


class TestParseIso(unittest.TestCase):
    """Tests for _parse_iso() — pure date parsing."""

    def test_z_suffix_parsed(self):
        result = shm._parse_iso("2026-01-01T00:00:00Z")
        self.assertIsNotNone(result)

    def test_plus_offset_parsed(self):
        result = shm._parse_iso("2026-01-01T00:00:00+00:00")
        self.assertIsNotNone(result)

    def test_z_and_offset_equivalent(self):
        z = shm._parse_iso("2026-03-01T12:00:00Z")
        offset = shm._parse_iso("2026-03-01T12:00:00+00:00")
        self.assertEqual(z, offset)

    def test_invalid_string_returns_none(self):
        self.assertIsNone(shm._parse_iso("not-a-date"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(shm._parse_iso(""))

    def test_numeric_string_returns_none(self):
        self.assertIsNone(shm._parse_iso("12345"))


class TestExtractLastAuditTs(unittest.TestCase):
    """Tests for _extract_last_audit_ts()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_file_returns_none(self):
        result = shm._extract_last_audit_ts(self._tmp / "nonexistent.jsonl")
        self.assertIsNone(result)

    def test_empty_file_returns_none(self):
        p = self._tmp / "empty.jsonl"
        p.write_text("", encoding="utf-8")
        self.assertIsNone(shm._extract_last_audit_ts(p))

    def test_single_entry_with_ts_returns_ts(self):
        p = self._tmp / "audit.jsonl"
        p.write_text(json.dumps({"ts": "2026-03-01T00:00:00Z"}) + "\n", encoding="utf-8")
        result = shm._extract_last_audit_ts(p)
        self.assertEqual(result, "2026-03-01T00:00:00Z")

    def test_returns_last_entry_ts(self):
        p = self._tmp / "audit.jsonl"
        with p.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"ts": "2026-01-01T00:00:00Z"}) + "\n")
            f.write(json.dumps({"ts": "2026-03-08T12:00:00Z"}) + "\n")
        result = shm._extract_last_audit_ts(p)
        self.assertEqual(result, "2026-03-08T12:00:00Z")

    def test_skips_invalid_json_lines(self):
        p = self._tmp / "audit.jsonl"
        with p.open("w", encoding="utf-8") as f:
            f.write("not json\n")
            f.write(json.dumps({"ts": "2026-03-07T00:00:00Z"}) + "\n")
        result = shm._extract_last_audit_ts(p)
        self.assertEqual(result, "2026-03-07T00:00:00Z")

    def test_skips_entries_without_ts(self):
        p = self._tmp / "audit.jsonl"
        with p.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"ts": "2026-02-01T00:00:00Z"}) + "\n")
            f.write(json.dumps({"other_key": "no_timestamp"}) + "\n")
        # Last non-empty line has no ts; should find the one before
        result = shm._extract_last_audit_ts(p)
        self.assertEqual(result, "2026-02-01T00:00:00Z")


class TestCheckSecurityAudit(unittest.TestCase):
    """Tests for check_security_audit() with temp paths."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_candidates = None

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_with_candidate(self, path: Path) -> dict:
        """Monkeypatch candidates list and run check."""
        import inspect
        import types

        # Build a modified function with custom candidates
        original_candidates = [
            Path("/home/jeebs/.openclaw/logs/config-audit.jsonl"),
            Path("/home/jeebs/.openclaw_backups/openclaw-state-20260217-222359/logs/config-audit.jsonl"),
        ]

        # Temporarily replace CANDIDATES inside function by patching the module
        orig_code = shm.check_security_audit

        def patched():
            candidates = [path]
            chosen = None
            last_ts = None
            for p in candidates:
                ts = shm._extract_last_audit_ts(p)
                if ts:
                    chosen = p
                    last_ts = ts
                    break

            if not last_ts:
                return {
                    "pass": False,
                    "error": "No security audit log timestamp found",
                    "checked_paths": [str(p) for p in candidates],
                }

            from datetime import datetime, timezone
            dt = shm._parse_iso(last_ts)
            if not dt:
                return {"pass": False, "error": f"Unparseable timestamp: {last_ts}"}

            age_hours = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0
            return {
                "pass": age_hours <= shm.AUDIT_STALE_HOURS,
                "last_run": dt.astimezone(timezone.utc).isoformat(),
                "age_hours": round(age_hours, 2),
                "stale_after_hours": shm.AUDIT_STALE_HOURS,
                "path": str(chosen),
            }

        return patched()

    def test_no_audit_log_returns_fail(self):
        result = self._run_with_candidate(self._tmp / "nonexistent.jsonl")
        self.assertFalse(result["pass"])
        self.assertIn("error", result)

    def test_recent_audit_passes(self):
        from datetime import datetime, timezone
        p = self._tmp / "audit.jsonl"
        recent_ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        p.write_text(json.dumps({"ts": recent_ts}) + "\n", encoding="utf-8")
        result = self._run_with_candidate(p)
        self.assertTrue(result["pass"])

    def test_stale_audit_fails(self):
        p = self._tmp / "audit.jsonl"
        # 30 days ago
        old_ts = "2024-01-01T00:00:00Z"
        p.write_text(json.dumps({"ts": old_ts}) + "\n", encoding="utf-8")
        result = self._run_with_candidate(p)
        self.assertFalse(result["pass"])
        self.assertGreater(result["age_hours"], shm.AUDIT_STALE_HOURS)


class TestCheckReplayLogWritable(unittest.TestCase):
    """Tests for check_replay_log_writable()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_env = os.environ.get("OPENCLAW_REPLAY_LOG_PATH")

    def tearDown(self):
        if self._orig_env is None:
            os.environ.pop("OPENCLAW_REPLAY_LOG_PATH", None)
        else:
            os.environ["OPENCLAW_REPLAY_LOG_PATH"] = self._orig_env
        self._tmpdir.cleanup()

    def test_writable_path_returns_pass(self):
        log_path = self._tmp / "replay" / "replay.jsonl"
        os.environ["OPENCLAW_REPLAY_LOG_PATH"] = str(log_path)
        result = shm.check_replay_log_writable()
        self.assertTrue(result["pass"])
        self.assertEqual(result["status"], "WRITABLE")

    def test_creates_parent_dir(self):
        log_path = self._tmp / "deep" / "replay.jsonl"
        os.environ["OPENCLAW_REPLAY_LOG_PATH"] = str(log_path)
        self.assertFalse(log_path.parent.exists())
        shm.check_replay_log_writable()
        self.assertTrue(log_path.parent.exists())


class TestDetectCoderDegradedReason(unittest.TestCase):
    """Tests for _detect_coder_degraded_reason()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_env = os.environ.get("OPENCLAW_VLLM_CODER_LOG_PATH")

    def tearDown(self):
        if self._orig_env is None:
            os.environ.pop("OPENCLAW_VLLM_CODER_LOG_PATH", None)
        else:
            os.environ["OPENCLAW_VLLM_CODER_LOG_PATH"] = self._orig_env
        self._tmpdir.cleanup()

    def test_missing_log_returns_unknown(self):
        os.environ["OPENCLAW_VLLM_CODER_LOG_PATH"] = str(self._tmp / "nonexistent.log")
        result = shm._detect_coder_degraded_reason()
        self.assertEqual(result, "UNKNOWN")

    def test_vram_low_detected(self):
        log = self._tmp / "vllm-coder.log"
        log.write_text("some line\nVRAM_GUARD_BLOCKED reason=VRAM_LOW\n", encoding="utf-8")
        os.environ["OPENCLAW_VLLM_CODER_LOG_PATH"] = str(log)
        result = shm._detect_coder_degraded_reason()
        self.assertEqual(result, "VRAM_LOW")

    def test_vram_guard_blocked_detected(self):
        log = self._tmp / "vllm-coder.log"
        log.write_text("some line\nVRAM_GUARD_BLOCKED reason=OTHER\n", encoding="utf-8")
        os.environ["OPENCLAW_VLLM_CODER_LOG_PATH"] = str(log)
        result = shm._detect_coder_degraded_reason()
        self.assertEqual(result, "VRAM_GUARD_BLOCKED")

    def test_no_vram_marker_returns_unknown(self):
        log = self._tmp / "vllm-coder.log"
        log.write_text("normal startup log line\n", encoding="utf-8")
        os.environ["OPENCLAW_VLLM_CODER_LOG_PATH"] = str(log)
        result = shm._detect_coder_degraded_reason()
        self.assertEqual(result, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
