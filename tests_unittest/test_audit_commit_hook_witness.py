import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import audit_commit_hook  # noqa: E402


class TestAuditCommitHookWitness(unittest.TestCase):
    def test_witness_commit_invoked_on_audit_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            captured = {}

            def _capture_commit(*, record, ledger_path):
                captured["record"] = dict(record)
                captured["ledger_path"] = str(ledger_path)
                return {"seq": 1, "hash": "h"}

            with patch.object(audit_commit_hook, "WORKSPACE_ROOT", root):
                with patch.object(audit_commit_hook, "DEFAULT_WITNESS_LEDGER_PATH", root / "state_runtime" / "teamchat" / "witness_ledger.jsonl"):
                    with patch.object(audit_commit_hook, "CHECKS", [("tests_pass", "x")]):
                        with patch.object(audit_commit_hook, "run_check", return_value=(True, "ok")):
                            with patch.object(audit_commit_hook, "witness_commit", side_effect=_capture_commit):
                                with patch.dict(os.environ, {"OPENCLAW_WITNESS_LEDGER": "1", "OPENCLAW_WITNESS_LEDGER_STRICT": "1"}, clear=False):
                                    ok = audit_commit_hook.audit_commit()
        self.assertTrue(ok)
        self.assertEqual(captured["record"]["event"], "governance_audit_commit")
        self.assertTrue(captured["ledger_path"].endswith("witness_ledger.jsonl"))

    def test_witness_failure_degrades_when_not_strict(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(audit_commit_hook, "WORKSPACE_ROOT", root):
                with patch.object(audit_commit_hook, "CHECKS", [("tests_pass", "x")]):
                    with patch.object(audit_commit_hook, "run_check", return_value=(True, "ok")):
                        with patch.object(audit_commit_hook, "witness_commit", side_effect=RuntimeError("boom")):
                            with patch.dict(os.environ, {"OPENCLAW_WITNESS_LEDGER": "1", "OPENCLAW_WITNESS_LEDGER_STRICT": "0"}, clear=False):
                                ok = audit_commit_hook.audit_commit()
        self.assertTrue(ok)

    def test_witness_failure_fails_closed_when_strict(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(audit_commit_hook, "WORKSPACE_ROOT", root):
                with patch.object(audit_commit_hook, "CHECKS", [("tests_pass", "x")]):
                    with patch.object(audit_commit_hook, "run_check", return_value=(True, "ok")):
                        with patch.object(audit_commit_hook, "witness_commit", side_effect=RuntimeError("boom")):
                            with patch.dict(os.environ, {"OPENCLAW_WITNESS_LEDGER": "1", "OPENCLAW_WITNESS_LEDGER_STRICT": "1"}, clear=False):
                                ok = audit_commit_hook.audit_commit()
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
