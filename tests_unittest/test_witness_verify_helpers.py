"""Tests for workspace/teamchat/witness_verify.py pure helpers.

Stubs the `message` import so the module loads without the real teamchat package.

Covers:
- _content_only_hash
- _session_id_from_path
- _load_jsonl
- default_ledger_path
"""
import hashlib
import importlib.util as _ilu
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEAMCHAT_DIR = REPO_ROOT / "workspace" / "teamchat"

# ---------------------------------------------------------------------------
# Stub `message` module — witness_verify falls back to `from message import`
# when the relative import fails (which it will, given we use spec_from_file_location)
# ---------------------------------------------------------------------------
_msg_stub = types.ModuleType("message")
_msg_stub.MESSAGE_HASH_VERSION_LEGACY = "legacy"
_msg_stub.MESSAGE_HASH_VERSION_V2 = "v2"
_msg_stub.canonical_message_hash_v2 = lambda **kw: "stubhash"
_msg_stub.legacy_message_hash = lambda **kw: "stubleghash"
sys.modules.setdefault("message", _msg_stub)

_spec = _ilu.spec_from_file_location(
    "witness_verify_real",
    str(TEAMCHAT_DIR / "witness_verify.py"),
)
wv = _ilu.module_from_spec(_spec)
sys.modules["witness_verify_real"] = wv
_spec.loader.exec_module(wv)


# ---------------------------------------------------------------------------
# _content_only_hash
# ---------------------------------------------------------------------------

class TestContentOnlyHash(unittest.TestCase):
    """Tests for _content_only_hash() — SHA-256 of message content field."""

    def test_known_content(self):
        msg = {"content": "hello"}
        expected = hashlib.sha256(b"hello").hexdigest()
        self.assertEqual(wv._content_only_hash(msg), expected)

    def test_empty_content(self):
        msg = {"content": ""}
        expected = hashlib.sha256(b"").hexdigest()
        self.assertEqual(wv._content_only_hash(msg), expected)

    def test_missing_content_key(self):
        msg = {"other": "field"}
        expected = hashlib.sha256(b"").hexdigest()
        self.assertEqual(wv._content_only_hash(msg), expected)

    def test_none_message(self):
        expected = hashlib.sha256(b"").hexdigest()
        self.assertEqual(wv._content_only_hash(None), expected)

    def test_returns_64_char_hex(self):
        result = wv._content_only_hash({"content": "test"})
        self.assertEqual(len(result), 64)
        int(result, 16)  # should not raise

    def test_different_content_different_hash(self):
        h1 = wv._content_only_hash({"content": "a"})
        h2 = wv._content_only_hash({"content": "b"})
        self.assertNotEqual(h1, h2)

    def test_deterministic(self):
        msg = {"content": "same"}
        self.assertEqual(wv._content_only_hash(msg), wv._content_only_hash(msg))


# ---------------------------------------------------------------------------
# _session_id_from_path
# ---------------------------------------------------------------------------

class TestSessionIdFromPath(unittest.TestCase):
    """Tests for _session_id_from_path() — extracts stem from path."""

    def test_stem_returned(self):
        p = Path("/some/dir/session-abc123.jsonl")
        result = wv._session_id_from_path(p)
        self.assertEqual(result, "session-abc123")

    def test_no_extension_stem(self):
        p = Path("/dir/mysession")
        result = wv._session_id_from_path(p)
        self.assertEqual(result, "mysession")

    def test_returns_string(self):
        result = wv._session_id_from_path(Path("/a/b.jsonl"))
        self.assertIsInstance(result, str)

    def test_complex_stem(self):
        p = Path("/a/b/2026-01-15T120000Z_session-XYZ.jsonl")
        result = wv._session_id_from_path(p)
        self.assertEqual(result, "2026-01-15T120000Z_session-XYZ")


# ---------------------------------------------------------------------------
# _load_jsonl
# ---------------------------------------------------------------------------

class TestLoadJsonl(unittest.TestCase):
    """Tests for _load_jsonl() — reads JSONL file into list of dicts."""

    def test_single_line(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text(json.dumps({"key": "val"}) + "\n", encoding="utf-8")
            result = wv._load_jsonl(p)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["key"], "val")

    def test_multiple_lines(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            lines = [json.dumps({"n": i}) for i in range(4)]
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = wv._load_jsonl(p)
            self.assertEqual(len(result), 4)
            self.assertEqual(result[2]["n"], 2)

    def test_blank_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text("\n\n" + json.dumps({"x": 1}) + "\n\n", encoding="utf-8")
            result = wv._load_jsonl(p)
            self.assertEqual(len(result), 1)

    def test_non_dict_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text(
                json.dumps([1, 2]) + "\n"
                + json.dumps({"ok": True}) + "\n",
                encoding="utf-8",
            )
            result = wv._load_jsonl(p)
            self.assertEqual(len(result), 1)
            self.assertTrue(result[0]["ok"])

    def test_empty_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text("", encoding="utf-8")
            result = wv._load_jsonl(p)
            self.assertEqual(result, [])

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text(json.dumps({"a": 1}) + "\n", encoding="utf-8")
            result = wv._load_jsonl(p)
            self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# default_ledger_path
# ---------------------------------------------------------------------------

class TestDefaultLedgerPath(unittest.TestCase):
    """Tests for default_ledger_path() — returns path under repo_root."""

    def test_contains_witness_ledger(self):
        result = wv.default_ledger_path(Path("/repo"))
        self.assertIn("witness_ledger.jsonl", str(result))

    def test_is_absolute(self):
        result = wv.default_ledger_path(Path("/repo"))
        self.assertTrue(result.is_absolute())

    def test_returns_path(self):
        result = wv.default_ledger_path(Path("/repo"))
        self.assertIsInstance(result, Path)

    def test_prefixed_with_repo_root(self):
        result = wv.default_ledger_path(Path("/myrepo"))
        self.assertTrue(str(result).startswith("/myrepo"))


if __name__ == "__main__":
    unittest.main()
