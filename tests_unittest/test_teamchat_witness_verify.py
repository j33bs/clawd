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

from teamchat.message import MESSAGE_HASH_VERSION_V2, canonical_message_hash_v2  # noqa: E402
from teamchat.witness_verify import verify_session_witness  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
