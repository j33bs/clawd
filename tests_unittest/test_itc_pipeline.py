import json
import tempfile
import unittest
from pathlib import Path

from core_infra.econ_log import append_jsonl
from scripts.sim_runner import compute_sim_b_tilt
from workspace.itc.api import get_itc_signal
from workspace.itc.ingest.interfaces import FileDropAdapter, ingest_with_adapter, validate_signal


class TestItcPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artifacts = self.root / "workspace" / "artifacts" / "itc"
        self.inbox = self.root / "workspace" / "data" / "itc" / "inbox"
        self.inbox.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_file_drop_parse_and_persist(self):
        raw_file = self.inbox / "signal.json"
        raw_file.write_text(
            json.dumps({
                "source": "file",
                "ts_utc": "2026-02-18T12:00:00Z",
                "window": "4h",
                "metrics": {
                    "sentiment": 0.35,
                    "confidence": 0.72,
                    "regime": "risk_on",
                    "risk_on": 0.65,
                    "risk_off": 0.35,
                },
            }),
            encoding="utf-8",
        )

        out = ingest_with_adapter(
            FileDropAdapter(inbox_dir=self.inbox, input_file=raw_file),
            run_id="test_run",
            artifact_root=self.artifacts,
        )
        self.assertIn("signal", out)
        self.assertTrue(Path(out["paths"]["raw_path"]).exists())
        self.assertTrue(Path(out["paths"]["normalized_path"]).exists())

        norm = json.loads(Path(out["paths"]["normalized_path"]).read_text(encoding="utf-8"))
        self.assertEqual(norm["schema_version"], 1)
        self.assertEqual(norm["metrics"]["sentiment"], 0.35)

    def test_validation_rejects_malformed(self):
        bad = {
            "schema_version": 1,
            "source": "file",
            "ts_utc": "bad-ts",
            "window": "4h",
            "metrics": {"sentiment": "high", "confidence": 0.5},
            "raw_ref": "x",
        }
        ok, reason = validate_signal(bad)
        self.assertFalse(ok)
        self.assertNotEqual(reason, "ok")

    def test_freshness_returns_stale(self):
        norm_dir = self.artifacts / "normalized" / "2026" / "02" / "17"
        norm_dir.mkdir(parents=True, exist_ok=True)
        stale = {
            "schema_version": 1,
            "source": "manual",
            "ts_utc": "2026-02-17T00:00:00Z",
            "window": "1d",
            "metrics": {
                "sentiment": 0.1,
                "confidence": 0.8,
                "regime": "risk_on",
                "risk_on": 0.55,
                "risk_off": 0.45,
            },
            "raw_ref": "workspace/artifacts/itc/raw/2026/02/17/manual_20260217T000000Z_abcd1234.json",
            "signature": "sha256:" + "a" * 64,
        }
        (norm_dir / "itc_signal_20260217T000000Z_abcd1234.json").write_text(
            json.dumps(stale),
            encoding="utf-8",
        )

        result = get_itc_signal(
            ts_utc="2026-02-18T12:00:00Z",
            lookback="4h",
            policy={"artifacts_root": str(self.artifacts), "run_id": "freshness_test"},
        )
        self.assertEqual(result["reason"], "stale")
        self.assertIsNone(result["signal"])

    def test_sim_b_tilt_is_bounded_and_logged(self):
        tilt = compute_sim_b_tilt(10.0, scale=0.005, max_abs_tilt=0.02)
        self.assertEqual(tilt, 0.02)

        econ_path = self.root / "economics" / "observe.jsonl"
        append_jsonl(
            str(econ_path),
            {
                "ts": "2026-02-18T12:00:00Z",
                "sim": "SIM_B",
                "type": "sim_b_tilt_applied",
                "payload": {
                    "sentiment": 10.0,
                    "tilt": tilt,
                    "reason": "ok",
                    "source": "manual",
                },
            },
        )
        lines = econ_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["type"], "sim_b_tilt_applied")
        self.assertEqual(payload["payload"]["tilt"], 0.02)


if __name__ == "__main__":
    unittest.main()
