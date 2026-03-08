"""Tests for phi_metrics_sync — _classify_audit, _format_row, _load_existing_rows,
_load_audit_files, and the sync() integration."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "workspace" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import phi_metrics_sync as pms


class TestClassifyAudit(unittest.TestCase):
    """Tests for _classify_audit() — experiment type detection."""

    def test_commit_gate_filename_is_inv004(self):
        data = {"_audit_file": "commit_gate_TASK_abc_20260101T000000Z.json"}
        self.assertEqual(pms._classify_audit(data), "INV-004")

    def test_gate_decision_field_is_inv004(self):
        data = {"_audit_file": "something.json", "gate_decision": "PASS"}
        self.assertEqual(pms._classify_audit(data), "INV-004")

    def test_being_divergence_filename_is_inv003(self):
        data = {"_audit_file": "being_divergence_20260226T033059Z.json"}
        self.assertEqual(pms._classify_audit(data), "INV-003")

    def test_experiment_inv003_field_is_inv003(self):
        data = {"_audit_file": "something.json", "experiment": "INV-003"}
        self.assertEqual(pms._classify_audit(data), "INV-003")

    def test_masking_filename_is_inv003b(self):
        data = {"_audit_file": "masking_variant_20260306.json"}
        self.assertEqual(pms._classify_audit(data), "INV-003b")

    def test_experiment_masking_variant_is_inv003b(self):
        data = {"_audit_file": "x.json", "experiment": "masking_variant"}
        self.assertEqual(pms._classify_audit(data), "INV-003b")

    def test_synergy_filename_is_inv001(self):
        data = {"_audit_file": "synergy_results.json"}
        self.assertEqual(pms._classify_audit(data), "INV-001")

    def test_experiment_inv001_is_inv001(self):
        data = {"_audit_file": "x.json", "experiment": "INV-001"}
        self.assertEqual(pms._classify_audit(data), "INV-001")

    def test_inv_id_field_used_as_experiment(self):
        data = {"_audit_file": "x.json", "inv_id": "INV-007"}
        self.assertEqual(pms._classify_audit(data), "INV-007")

    def test_unclassifiable_returns_none(self):
        data = {"_audit_file": "random_file.json"}
        self.assertIsNone(pms._classify_audit(data))


class TestFormatRow(unittest.TestCase):
    """Tests for _format_row() — markdown table row generation."""

    def _inv004_data(self):
        return {
            "task_id": "TASK_TEST_001",
            "timestamp_utc": "2026-03-08T12:00:00Z",
            "gate_decision": "PASS",
            "novelty": {"theta": 0.15, "dist_joint_vs_c_lawd": 0.8, "dist_joint_vs_dali": 0.7},
            "env": {"embed_model": "all-MiniLM-L6-v2", "sanitizer_version": "1.0.0"},
            "isolation": {"isolation_verified": True},
        }

    def test_inv004_row_starts_with_pipe(self):
        row = pms._format_row(self._inv004_data(), "INV-004")
        self.assertTrue(row.startswith("| INV-004"))

    def test_inv004_contains_task_id(self):
        row = pms._format_row(self._inv004_data(), "INV-004")
        self.assertIn("TASK_TEST_001", row)

    def test_inv004_contains_gate_decision(self):
        row = pms._format_row(self._inv004_data(), "INV-004")
        self.assertIn("PASS", row)

    def test_inv004_contains_theta(self):
        row = pms._format_row(self._inv004_data(), "INV-004")
        self.assertIn("θ=0.15", row)

    def test_inv003_row_format(self):
        data = {
            "task_id": "being_divergence_20260226",
            "timestamp_utc": "2026-02-26T03:30:00Z",
            "verdict": "SITUATIONAL",
            "accuracy": 0.893,
            "author_silhouette": -0.009,
            "topic_silhouette": 0.047,
        }
        row = pms._format_row(data, "INV-003")
        self.assertIn("INV-003", row)
        self.assertIn("SITUATIONAL", row)
        self.assertIn("accuracy=0.893", row)

    def test_inv003b_row_format(self):
        data = {
            "task_id": "masking_20260306",
            "timestamp_utc": "2026-03-06T00:00:00Z",
            "verdict": "CENTROID-DISPOSITIONAL",
            "dispositional_attractor": "PASS",
            "style_consistency": "FAIL",
            "corpus_size": 23,
            "n_beings": 8,
        }
        row = pms._format_row(data, "INV-003b")
        self.assertIn("INV-003b", row)
        self.assertIn("CENTROID-DISPOSITIONAL", row)
        self.assertIn("corpus_size=23", row)

    def test_inv001_row_format(self):
        data = {
            "task_id": "synergy_20260201",
            "timestamp_utc": "2026-02-01T00:00:00Z",
            "result": "NULL",
            "synergy_delta": -0.024,
            "phase": "cold_start",
        }
        row = pms._format_row(data, "INV-001")
        self.assertIn("INV-001", row)
        self.assertIn("synergy_Δ=-0.024", row)
        self.assertIn("phase=cold_start", row)

    def test_unknown_exp_produces_generic_row(self):
        data = {
            "task_id": "custom_exp_001",
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "result": "PASS",
        }
        row = pms._format_row(data, "INV-009")
        self.assertIn("INV-009", row)
        self.assertIn("PASS", row)

    def test_date_extracted_from_timestamp(self):
        data = {
            "task_id": "x",
            "timestamp_utc": "2026-03-08T12:00:00Z",
            "gate_decision": "PASS",
            "novelty": {}, "env": {}, "isolation": {},
        }
        row = pms._format_row(data, "INV-004")
        self.assertIn("2026-03-08", row)


class TestLoadExistingRows(unittest.TestCase):
    """Tests for _load_existing_rows()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_file_returns_empty_set(self):
        result = pms._load_existing_rows(self._tmp / "nonexistent.md")
        self.assertEqual(result, set())

    def test_task_id_extracted(self):
        phi = self._tmp / "phi.md"
        phi.write_text("| INV-004 | TASK_ABC_001 | 2026 | PASS |\n", encoding="utf-8")
        result = pms._load_existing_rows(phi)
        self.assertIn("TASK_ABC_001", result)

    def test_inv_id_extracted(self):
        phi = self._tmp / "phi.md"
        phi.write_text("| INV-003 | being_divergence_20260226 | 2026 | SITUATIONAL |\n",
                       encoding="utf-8")
        result = pms._load_existing_rows(phi)
        self.assertIn("INV-003", result)

    def test_multiple_ids_extracted(self):
        phi = self._tmp / "phi.md"
        phi.write_text(
            "| INV-001 | TASK_X_001 | 2026 |\n"
            "| INV-003 | TASK_Y_002 | 2026 |\n",
            encoding="utf-8",
        )
        result = pms._load_existing_rows(phi)
        self.assertIn("TASK_X_001", result)
        self.assertIn("TASK_Y_002", result)


class TestLoadAuditFiles(unittest.TestCase):
    """Tests for _load_audit_files()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_dir_returns_empty(self):
        result = pms._load_audit_files(self._tmp / "nonexistent")
        self.assertEqual(result, [])

    def test_loads_json_files(self):
        audit_dir = self._tmp / "audit"
        audit_dir.mkdir()
        (audit_dir / "exp1.json").write_text(json.dumps({"exp": "test"}), encoding="utf-8")
        result = pms._load_audit_files(audit_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["exp"], "test")

    def test_adds_audit_file_name(self):
        audit_dir = self._tmp / "audit"
        audit_dir.mkdir()
        (audit_dir / "commit_gate_TASK_001.json").write_text(
            json.dumps({"gate_decision": "PASS"}), encoding="utf-8"
        )
        result = pms._load_audit_files(audit_dir)
        self.assertEqual(result[0]["_audit_file"], "commit_gate_TASK_001.json")

    def test_invalid_json_skipped(self):
        audit_dir = self._tmp / "audit"
        audit_dir.mkdir()
        (audit_dir / "bad.json").write_text("not json!", encoding="utf-8")
        (audit_dir / "good.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
        result = pms._load_audit_files(audit_dir)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["ok"])

    def test_non_json_files_ignored(self):
        audit_dir = self._tmp / "audit"
        audit_dir.mkdir()
        (audit_dir / "notes.txt").write_text("not a json file", encoding="utf-8")
        (audit_dir / "data.json").write_text(json.dumps({"x": 1}), encoding="utf-8")
        result = pms._load_audit_files(audit_dir)
        self.assertEqual(len(result), 1)


class TestSync(unittest.TestCase):
    """Integration tests for sync()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._audit_dir = self._tmp / "audit"
        self._audit_dir.mkdir()
        self._phi_path = self._tmp / "governance" / "phi_metrics.md"
        self._phi_path.parent.mkdir(parents=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_audit(self, name: str, data: dict) -> None:
        (self._audit_dir / name).write_text(json.dumps(data), encoding="utf-8")

    def test_sync_creates_phi_metrics_if_missing(self):
        result = pms.sync(self._audit_dir, self._phi_path)
        self.assertTrue(self._phi_path.exists())

    def test_dry_run_does_not_write_rows(self):
        self._write_audit("commit_gate_TASK_001.json", {
            "task_id": "TASK_001",
            "gate_decision": "PASS",
            "novelty": {}, "env": {}, "isolation": {},
            "timestamp_utc": "2026-03-08T00:00:00Z",
        })
        result = pms.sync(self._audit_dir, self._phi_path, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertGreater(result["appended_count"], 0)
        # In dry_run mode, content should only have the header (not the appended rows)
        content = self._phi_path.read_text(encoding="utf-8")
        self.assertNotIn("TASK_001", content)

    def test_sync_appends_inv004_row(self):
        self._write_audit("commit_gate_TASK_999.json", {
            "task_id": "TASK_999",
            "gate_decision": "PASS",
            "novelty": {"theta": 0.17}, "env": {}, "isolation": {},
            "timestamp_utc": "2026-03-08T00:00:00Z",
        })
        result = pms.sync(self._audit_dir, self._phi_path)
        self.assertEqual(result["appended_count"], 1)
        content = self._phi_path.read_text(encoding="utf-8")
        self.assertIn("TASK_999", content)
        self.assertIn("PASS", content)

    def test_sync_skips_already_present_rows(self):
        # Write a phi file that already has TASK_999
        self._phi_path.write_text(
            "| INV-004 | TASK_999 | 2026-03-08 | PASS | θ=0.17 | — | — | — | — |\n",
            encoding="utf-8",
        )
        self._write_audit("commit_gate_TASK_999.json", {
            "task_id": "TASK_999",
            "gate_decision": "PASS",
            "novelty": {}, "env": {}, "isolation": {},
            "timestamp_utc": "2026-03-08T00:00:00Z",
        })
        result = pms.sync(self._audit_dir, self._phi_path)
        self.assertEqual(result["appended_count"], 0)
        self.assertGreaterEqual(result["skipped_count"], 1)

    def test_sync_returns_audit_files_scanned_count(self):
        self._write_audit("a.json", {"gate_decision": "PASS", "timestamp_utc": "2026-01-01T00:00:00Z"})
        self._write_audit("b.json", {"gate_decision": "FAIL", "timestamp_utc": "2026-01-01T00:00:00Z"})
        result = pms.sync(self._audit_dir, self._phi_path)
        self.assertEqual(result["audit_files_scanned"], 2)

    def test_sync_unclassifiable_files_not_appended(self):
        self._write_audit("random_data.json", {"some_field": "no experiment marker"})
        result = pms.sync(self._audit_dir, self._phi_path)
        self.assertEqual(result["appended_count"], 0)


if __name__ == "__main__":
    unittest.main()
