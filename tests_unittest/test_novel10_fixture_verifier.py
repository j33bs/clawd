from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_contract_module():
    path = REPO_ROOT / "workspace" / "tacti_cr" / "novel10_contract.py"
    spec = importlib.util.spec_from_file_location("novel10_contract", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_verifier_module():
    path = REPO_ROOT / "workspace" / "scripts" / "verify_tacti_cr_novel10_fixture.py"
    spec = importlib.util.spec_from_file_location("verify_novel10_fixture", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestNovel10FixtureVerifier(unittest.TestCase):
    def test_verifier_passes_with_minimal_events(self):
        contract = _load_contract_module()
        verifier = _load_verifier_module()
        required = contract.required_for_fixture(repo_root=REPO_ROOT, include_ui=False)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "events.jsonl"
            with path.open("w", encoding="utf-8") as f:
                for events in required.values():
                    for event_type in events:
                        row = {
                            "ts": "2026-02-19T13:00:00Z",
                            "type": event_type,
                            "payload": {"fixture": True},
                            "schema": 1,
                        }
                        f.write(json.dumps(row, ensure_ascii=True) + "\n")
            ok, missing, counts = verifier.verify_events(path, include_ui=False, min_count=1)
            self.assertTrue(ok)
            self.assertEqual([], missing)
            for events in required.values():
                for event_type in events:
                    self.assertGreaterEqual(counts.get(event_type, 0), 1)

    def test_verifier_fails_missing_event(self):
        contract = _load_contract_module()
        required = contract.required_for_fixture(repo_root=REPO_ROOT, include_ui=False)
        all_types = [event for events in required.values() for event in events]
        omitted = all_types[0]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "events.jsonl"
            with path.open("w", encoding="utf-8") as f:
                for event_type in all_types[1:]:
                    row = {
                        "ts": "2026-02-19T13:00:00Z",
                        "type": event_type,
                        "payload": {"fixture": True},
                        "schema": 1,
                    }
                    f.write(json.dumps(row, ensure_ascii=True) + "\n")

            proc = subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "workspace" / "scripts" / "verify_tacti_cr_novel10_fixture.py"),
                    "--events-path",
                    str(path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("missing_event_types=", proc.stderr)
            self.assertIn(omitted, proc.stderr)


if __name__ == "__main__":
    unittest.main()
