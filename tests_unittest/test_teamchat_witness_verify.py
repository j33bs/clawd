import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace"))
if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from teamchat.message import (  # noqa: E402
    MESSAGE_HASH_VERSION_V2,
    agent_role,
    canonical_message_hash,
    canonical_message_hash_v2,
    canonical_message_payload,
    legacy_message_hash,
    make_message,
    utc_now,
    _route_minimal,
)
from teamchat.witness_verify import (  # noqa: E402
    _content_only_hash,
    _expected_hashes,
    _index_session_messages,
    _load_jsonl,
    _session_id_from_path,
    default_ledger_path,
    verify_session_witness,
)
from witness_ledger import commit  # noqa: E402


def _agent_row(*, session_id: str, turn: int, agent: str, content: str, ts: str) -> dict:
    route = {"provider": "mock_provider", "model": "mock_model", "reason_code": "success", "attempts": 1}
    return {
        "ts": ts,
        "role": f"agent:{agent}",
        "content": content,
        "route": route,
        "meta": {
            "session_id": session_id,
            "turn": turn,
            "agent": agent,
            "intent": f"teamchat:{agent}",
        },
    }


class TestTeamChatWitnessVerify(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(r, ensure_ascii=True) for r in rows) + "\n", encoding="utf-8")

    def _build_valid_fixture(self, root: Path) -> tuple[Path, Path]:
        session_id = "fixture_session"
        session_path = root / "workspace" / "state_runtime" / "teamchat" / "sessions" / f"{session_id}.jsonl"
        ledger_path = root / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
        rows = [
            {"ts": "2026-02-20T00:00:00Z", "role": "user", "content": "hello"},
            _agent_row(session_id=session_id, turn=1, agent="planner", content="planner reply", ts="2026-02-20T00:00:01Z"),
            _agent_row(session_id=session_id, turn=2, agent="coder", content="coder reply", ts="2026-02-20T00:00:02Z"),
        ]
        self._write_jsonl(session_path, rows)
        for row in rows:
            if not str(row.get("role", "")).startswith("agent:"):
                continue
            turn = int((row.get("meta", {}) or {}).get("turn", 0))
            agent = str((row.get("meta", {}) or {}).get("agent", ""))
            record = {
                "event": "teamchat_turn",
                "session_id": session_id,
                "turn": turn,
                "agent": agent,
                "route": dict(row.get("route", {}) or {}),
                "message_hash_version": MESSAGE_HASH_VERSION_V2,
                "message_hash": canonical_message_hash_v2(row, session_id=session_id, turn=turn),
                "ts": str(row.get("ts", "")),
            }
            commit(record=record, ledger_path=str(ledger_path), timestamp_utc=f"2026-02-20T00:00:0{turn}Z")
        return session_path, ledger_path

    def test_verify_passes_for_intact_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            session_path, ledger_path = self._build_valid_fixture(Path(td))
            result = verify_session_witness(session_path, ledger_path)
        self.assertTrue(result.ok)
        self.assertEqual(result.session_id, "fixture_session")
        self.assertEqual(result.witnessed_events, 2)
        self.assertTrue(result.head_hash)

    def test_verify_fails_on_tampered_ledger_entry(self):
        with tempfile.TemporaryDirectory() as td:
            session_path, ledger_path = self._build_valid_fixture(Path(td))
            rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            rows[0]["record"]["message_hash"] = "tampered"
            self._write_jsonl(ledger_path, rows)
            result = verify_session_witness(session_path, ledger_path)
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "ledger_chain_invalid")

    def test_verify_fails_when_session_line_is_modified(self):
        with tempfile.TemporaryDirectory() as td:
            session_path, ledger_path = self._build_valid_fixture(Path(td))
            rows = [json.loads(line) for line in session_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            rows[2]["content"] = "coder reply tampered"
            self._write_jsonl(session_path, rows)
            result = verify_session_witness(session_path, ledger_path)
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "message_hash_mismatch")

    def test_verify_fails_when_ledger_references_missing_session(self):
        with tempfile.TemporaryDirectory() as td:
            session_path, ledger_path = self._build_valid_fixture(Path(td))
            bad_record = {
                "event": "teamchat_turn",
                "session_id": "missing_session",
                "turn": 1,
                "agent": "planner",
                "route": {},
                "message_hash": "x",
                "message_hash_version": MESSAGE_HASH_VERSION_V2,
                "ts": "2026-02-20T00:00:10Z",
            }
            commit(record=bad_record, ledger_path=str(ledger_path), timestamp_utc="2026-02-20T00:00:10Z")
            result = verify_session_witness(session_path, ledger_path)
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "referenced_session_missing")

    def test_verify_fails_on_reordered_entries(self):
        with tempfile.TemporaryDirectory() as td:
            session_path, ledger_path = self._build_valid_fixture(Path(td))
            rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            rows.reverse()
            self._write_jsonl(ledger_path, rows)
            result = verify_session_witness(session_path, ledger_path)
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "ledger_chain_invalid")


class TestMessagePureFunctions(unittest.TestCase):
    """Tests for teamchat.message pure helpers."""

    # --- utc_now ---

    def test_utc_now_returns_string(self):
        self.assertIsInstance(utc_now(), str)

    def test_utc_now_ends_with_z(self):
        self.assertTrue(utc_now().endswith("Z"))

    def test_utc_now_contains_t(self):
        self.assertIn("T", utc_now())

    # --- agent_role ---

    def test_agent_role_prefixed(self):
        self.assertEqual(agent_role("planner"), "agent:planner")

    def test_agent_role_strips_whitespace(self):
        self.assertEqual(agent_role("  coder  "), "agent:coder")

    def test_agent_role_returns_string(self):
        self.assertIsInstance(agent_role("x"), str)

    # --- make_message ---

    def test_make_message_has_required_keys(self):
        msg = make_message(role="user", content="hello", ts="2026-01-01T00:00:00Z")
        self.assertIn("ts", msg)
        self.assertIn("role", msg)
        self.assertIn("content", msg)

    def test_make_message_role_stored(self):
        msg = make_message(role="user", content="hi")
        self.assertEqual(msg["role"], "user")

    def test_make_message_content_stored(self):
        msg = make_message(role="user", content="hi there")
        self.assertEqual(msg["content"], "hi there")

    def test_make_message_route_optional(self):
        msg = make_message(role="user", content="hi")
        self.assertNotIn("route", msg)

    def test_make_message_route_included_when_provided(self):
        msg = make_message(role="agent:planner", content="done", route={"provider": "mock"})
        self.assertIn("route", msg)

    def test_make_message_ts_auto_generated(self):
        msg = make_message(role="user", content="hi")
        self.assertIn("T", msg["ts"])

    # --- _route_minimal ---

    def test_route_minimal_extracts_provider(self):
        result = _route_minimal({"provider": "gpt", "model": "m", "other": "ignored"})
        self.assertEqual(result["provider"], "gpt")

    def test_route_minimal_none_returns_empty(self):
        result = _route_minimal(None)
        self.assertIsInstance(result, dict)

    def test_route_minimal_excludes_none_values(self):
        result = _route_minimal({"provider": "gpt", "model": None})
        self.assertNotIn("model", result)

    # --- canonical_message_payload ---

    def test_payload_has_session_id(self):
        msg = {"ts": "t", "role": "user", "content": "c"}
        p = canonical_message_payload(msg, session_id="sess-1", turn=1)
        self.assertEqual(p["session_id"], "sess-1")

    def test_payload_turn_defaults_to_zero(self):
        msg = {"ts": "t", "role": "user", "content": "c"}
        p = canonical_message_payload(msg)
        self.assertEqual(p["turn"], 0)

    def test_payload_has_content(self):
        msg = {"ts": "t", "role": "user", "content": "hello"}
        p = canonical_message_payload(msg)
        self.assertEqual(p["content"], "hello")

    # --- canonical_message_hash_v2 ---

    def test_hash_v2_returns_64_hex(self):
        msg = {"ts": "t", "role": "user", "content": "hi"}
        h = canonical_message_hash_v2(msg)
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_hash_v2_deterministic(self):
        msg = {"ts": "t", "role": "user", "content": "hi"}
        self.assertEqual(canonical_message_hash_v2(msg, session_id="s", turn=1),
                         canonical_message_hash_v2(msg, session_id="s", turn=1))

    def test_hash_v2_changes_with_session_id(self):
        msg = {"ts": "t", "role": "user", "content": "hi"}
        self.assertNotEqual(canonical_message_hash_v2(msg, session_id="a"),
                            canonical_message_hash_v2(msg, session_id="b"))

    # --- legacy_message_hash / canonical_message_hash ---

    def test_legacy_hash_returns_64_hex(self):
        msg = {"ts": "t", "role": "user", "content": "hi"}
        self.assertEqual(len(legacy_message_hash(msg)), 64)

    def test_canonical_hash_equals_legacy(self):
        msg = {"ts": "t", "role": "user", "content": "hi"}
        self.assertEqual(canonical_message_hash(msg), legacy_message_hash(msg))

    def test_legacy_hash_deterministic(self):
        msg = {"ts": "t", "role": "user", "content": "hi"}
        self.assertEqual(legacy_message_hash(msg), legacy_message_hash(msg))


class TestWitnessVerifyPureFunctions(unittest.TestCase):
    """Tests for teamchat.witness_verify pure helpers."""

    # --- _content_only_hash ---

    def test_content_only_hash_returns_64_hex(self):
        msg = {"content": "hello world"}
        h = _content_only_hash(msg)
        self.assertEqual(len(h), 64)

    def test_content_only_hash_deterministic(self):
        msg = {"content": "hello"}
        self.assertEqual(_content_only_hash(msg), _content_only_hash(msg))

    def test_content_only_hash_changes_with_content(self):
        self.assertNotEqual(_content_only_hash({"content": "a"}),
                            _content_only_hash({"content": "b"}))

    def test_content_only_hash_missing_content(self):
        # Empty content → valid hash
        self.assertEqual(len(_content_only_hash({})), 64)

    # --- _session_id_from_path ---

    def test_session_id_is_stem(self):
        p = Path("/some/dir/my_session.jsonl")
        self.assertEqual(_session_id_from_path(p), "my_session")

    def test_session_id_strips_extension(self):
        p = Path("/foo/bar_session.jsonl")
        result = _session_id_from_path(p)
        self.assertNotIn(".jsonl", result)

    # --- _load_jsonl ---

    def test_load_jsonl_valid_lines(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
            result = _load_jsonl(p)
            self.assertEqual(len(result), 2)

    def test_load_jsonl_skips_non_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('["list"]\n{"ok": true}\n', encoding="utf-8")
            result = _load_jsonl(p)
            self.assertEqual(len(result), 1)

    def test_load_jsonl_skips_blank_lines(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('{"a": 1}\n\n{"b": 2}\n', encoding="utf-8")
            result = _load_jsonl(p)
            self.assertEqual(len(result), 2)

    def test_load_jsonl_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text("{}\n", encoding="utf-8")
            self.assertIsInstance(_load_jsonl(p), list)

    # --- default_ledger_path ---

    def test_default_ledger_path_ends_with_jsonl(self):
        result = default_ledger_path(Path("/some/root"))
        self.assertTrue(str(result).endswith(".jsonl"))

    def test_default_ledger_path_under_repo_root(self):
        root = Path("/some/root")
        result = default_ledger_path(root)
        self.assertTrue(str(result).startswith(str(root)))

    # --- _index_session_messages ---

    def _agent_msg(self, *, session_id, turn, agent, content):
        return {
            "ts": "2026-01-01T00:00:00Z",
            "role": f"agent:{agent}",
            "content": content,
            "meta": {"session_id": session_id, "turn": turn},
        }

    def test_index_returns_dict(self):
        rows = [self._agent_msg(session_id="s", turn=1, agent="a", content="c")]
        indexed, _ = _index_session_messages(rows)
        self.assertIsInstance(indexed, dict)

    def test_index_user_rows_skipped(self):
        rows = [{"ts": "t", "role": "user", "content": "hi"}]
        indexed, _ = _index_session_messages(rows)
        self.assertEqual(len(indexed), 0)

    def test_index_agent_rows_indexed(self):
        rows = [self._agent_msg(session_id="s", turn=1, agent="a", content="c")]
        indexed, _ = _index_session_messages(rows)
        self.assertEqual(len(indexed), 1)

    def test_index_key_is_tuple(self):
        rows = [self._agent_msg(session_id="s", turn=1, agent="a", content="c")]
        indexed, _ = _index_session_messages(rows)
        key = list(indexed.keys())[0]
        self.assertIsInstance(key, tuple)

    # --- _expected_hashes ---

    def test_expected_hashes_returns_dict(self):
        msg = {"ts": "t", "role": "agent:a", "content": "c", "meta": {}}
        result = _expected_hashes(msg, session_id="s", turn=1)
        self.assertIsInstance(result, dict)

    def test_expected_hashes_has_content_only(self):
        msg = {"ts": "t", "role": "agent:a", "content": "c", "meta": {}}
        result = _expected_hashes(msg, session_id="s", turn=1)
        self.assertIn("content-only", result)

    def test_expected_hashes_values_are_hex(self):
        msg = {"ts": "t", "role": "agent:a", "content": "c", "meta": {}}
        result = _expected_hashes(msg, session_id="s", turn=1)
        for h in result.values():
            self.assertTrue(all(c in "0123456789abcdef" for c in h))


if __name__ == "__main__":
    unittest.main()
