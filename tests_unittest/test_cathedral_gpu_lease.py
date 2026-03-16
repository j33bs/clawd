import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
import sys
import socket
import json


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import FishTankRenderer
from cathedral.gpu_lease import GPULease
class TestCathedralGpuLease(unittest.TestCase):
    def test_gpu_lease_acquire_renew_release(self):
        with tempfile.TemporaryDirectory() as td:
            lease_path = Path(td) / "gpu_lease.json"
            lease = GPULease(path=lease_path)
            self.assertTrue(lease.acquire(owner="owner-a", mode="exclusive", ttl_s=10.0, policy="exclusive"))
            self.assertFalse(lease.acquire(owner="owner-b", mode="exclusive", ttl_s=10.0, policy="exclusive"))
            self.assertTrue(lease.renew(owner="owner-a", ttl_s=10.0))
            current = lease.current()
            self.assertEqual(current.get("owner"), "owner-a")
            self.assertTrue(float(current.get("expiry_ts", 0.0)) > time.time())
            self.assertTrue(lease.release(owner="owner-a"))
            self.assertFalse(lease_path.exists())

    def test_feature_masking_quiesced_removes_model_metrics(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.shader_params = {"luminosity": 0.5, "turbulence": 0.4, "velocity": 0.4, "nebula": 0.3, "warmth": 0.3, "vortex": 0.2, "ripple": 0.2, "cloud": 0.2}
        renderer._rd_inject_seed = 0.0
        renderer.set_runtime_context(lease_mode="exclusive", inference_quiesced=True)
        telemetry = {
            "gpu_temp": 42.0,
            "gpu_util": 0.33,
            "gpu_vram": 0.44,
            "gpu_vram_used_mb": 1024.0,
            "fan_gpu": 1200,
            "disk_io": 0.1,
            "network_throughput": 0.2,
            "kv_cache_mb": 2048.0,
            "local_model_loading": True,
            "model_vram_mb_by_process": {"model": 2048.0},
        }
        tacti = {"arousal": 0.4, "memory_recall_density": 0.1, "token_flux": 0.77}
        renderer.update_signals(telemetry, tacti)
        self.assertIn("token_flux", renderer.features_masked)
        self.assertFalse(renderer.features["token_flux"]["present"])
        self.assertEqual(renderer.features["token_flux"]["value"], 0.0)
        self.assertEqual(renderer.novelty_seed_source, "hardware")

    def test_novelty_seed_hardware_only_when_quiesced(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.shader_params = {"turbulence": 0.4, "vortex": 0.3, "nebula": 0.3, "cloud": 0.2}
        renderer.control_values = {"mutation_rate": 1.0}
        renderer.curiosity_impulses = []
        renderer.frame_index = 0
        renderer.signals = mock.Mock(gpu_temp=41.0, gpu_util=0.5, gpu_vram_used_mb=900.0, fan_speed=1300.0, disk_io=0.1)
        renderer.log = mock.Mock()
        renderer.novelty_seed_source = "hardware"
        with mock.patch("cathedral.fishtank_renderer.random.Random") as random_ctor:
            random_ctor.return_value = mock.Mock(uniform=mock.Mock(return_value=0.0))
            renderer.dream_cycle()
        self.assertTrue(random_ctor.called)

    def test_gpu_lease_reclaims_dead_owner(self):
        with tempfile.TemporaryDirectory() as td:
            lease_path = Path(td) / "gpu_lease.json"
            lease_path.write_text(
                json.dumps(
                    {
                        "owner": "owner-a",
                        "holders": ["owner-a"],
                        "host": socket.gethostname(),
                        "pid": 999999,
                        "expiry_ts": time.time() + 120.0,
                        "policy": "exclusive",
                    }
                ),
                encoding="utf-8",
            )
            lease = GPULease(path=lease_path)
            with mock.patch.object(lease, "_pid_alive", return_value=False):
                self.assertTrue(lease.acquire(owner="owner-b", mode="exclusive", ttl_s=10.0, policy="exclusive"))
            current = lease.current()
            self.assertEqual(current.get("owner"), "owner-b")

    def test_gpu_lease_reclaims_reused_pid_for_nonmatching_process(self):
        with tempfile.TemporaryDirectory() as td:
            lease_path = Path(td) / "gpu_lease.json"
            lease_path.write_text(
                json.dumps(
                    {
                        "owner": f"dali-fishtank:{socket.gethostname()}:4321",
                        "holders": [f"dali-fishtank:{socket.gethostname()}:4321"],
                        "host": socket.gethostname(),
                        "pid": 4321,
                        "expiry_ts": time.time() + 120.0,
                        "policy": "exclusive",
                    }
                ),
                encoding="utf-8",
            )
            lease = GPULease(path=lease_path)
            with mock.patch.object(lease, "_pid_alive", return_value=True):
                with mock.patch.object(lease, "_pid_cmdline", return_value="/usr/bin/python3 unrelated_worker.py"):
                    self.assertTrue(lease.acquire(owner="owner-b", mode="exclusive", ttl_s=10.0, policy="exclusive"))
            current = lease.current()
            self.assertEqual(current.get("owner"), "owner-b")


if __name__ == "__main__":
    unittest.main()
