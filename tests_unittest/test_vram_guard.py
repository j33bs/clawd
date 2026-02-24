import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vram_guard  # noqa: E402


class _CP:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestVramGuard(unittest.TestCase):
    def test_parse_nvidia_smi_csv(self):
        rows = vram_guard.parse_nvidia_smi_csv("24576, 12000\n24576, 4000\n")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["free_mb"], 12576)
        self.assertEqual(rows[1]["free_mb"], 20576)

    def test_threshold_behavior_low_vram(self):
        with patch.object(vram_guard.subprocess, "run", return_value=_CP(stdout="24576, 22000\n")):
            out = vram_guard.evaluate_vram_guard(min_free_mb=7000, allow_no_nvidia_smi=False)
        self.assertFalse(out["ok"], out)
        self.assertEqual(out["reason"], "VRAM_LOW")

    def test_threshold_behavior_ok(self):
        with patch.object(vram_guard.subprocess, "run", return_value=_CP(stdout="24576, 10000\n")):
            out = vram_guard.evaluate_vram_guard(min_free_mb=7000, allow_no_nvidia_smi=False)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["reason"], "OK")

    def test_missing_nvidia_smi_blocked_by_default(self):
        with patch.object(vram_guard.subprocess, "run", side_effect=FileNotFoundError()):
            out = vram_guard.evaluate_vram_guard(min_free_mb=7000, allow_no_nvidia_smi=False)
        self.assertFalse(out["ok"], out)
        self.assertEqual(out["reason"], "NVIDIA_SMI_MISSING")

    def test_missing_nvidia_smi_allowed_by_flag(self):
        with patch.object(vram_guard.subprocess, "run", side_effect=FileNotFoundError()):
            out = vram_guard.evaluate_vram_guard(min_free_mb=7000, allow_no_nvidia_smi=True)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["reason"], "NO_NVIDIA_SMI_ALLOWED")


if __name__ == "__main__":
    unittest.main()
