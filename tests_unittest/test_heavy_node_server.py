"""Tests for heavy-node server validation and health visibility."""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.runtime.heavy_node.server import AnswerRequest, CodeRequest, create_app  # noqa: E402


class HealthyWarmupRouter:
    def warmup(self):
        return {
            "hint": {"status": "ok", "latency_ms": 4, "model": "stub-hint", "backend": "stub"},
            "answer": {"status": "ok", "latency_ms": 6, "model": "stub-answer", "backend": "stub"},
        }

    def health(self):
        return {
            "status": "ok",
            "models": {
                "hint": {"status": "ok", "model": "stub-hint"},
                "answer": {"status": "ok", "model": "stub-answer"},
            },
        }

    def run_role(self, **_kwargs):
        raise AssertionError("run_role should not be called in these tests")


class FailingWarmupRouter(HealthyWarmupRouter):
    def warmup(self):
        raise RuntimeError("warmup exploded")


class TestHeavyNodeRequestValidation(unittest.TestCase):
    def test_answer_request_rejects_excessive_max_tokens(self):
        with self.assertRaises(ValidationError):
            AnswerRequest(prompt="hello", max_tokens=4096)

    def test_answer_request_rejects_temperature_above_one(self):
        with self.assertRaises(ValidationError):
            AnswerRequest(prompt="hello", temperature=1.5)

    def test_code_request_rejects_too_many_files(self):
        with self.assertRaises(ValidationError):
            CodeRequest(
                prompt="patch this",
                files=[{"path": f"f{i}.py", "content": "print(1)"} for i in range(9)],
            )


class TestHeavyNodeHealthWarmup(unittest.TestCase):
    def _await_warmup(self, client: TestClient) -> dict:
        for _ in range(20):
            payload = client.get("/health").json()
            if payload["warmup"]["completed_at"]:
                return payload
            time.sleep(0.02)
        self.fail("warmup did not complete in time")

    def test_health_exposes_completed_warmup_details(self):
        with mock.patch.dict(os.environ, {"DALI_HEAVY_NODE_DISABLE_STARTUP_WARMUP": "0"}, clear=False):
            with TestClient(create_app(router=HealthyWarmupRouter())) as client:
                payload = self._await_warmup(client)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["warmup"]["status"], "ok")
        self.assertIsNotNone(payload["warmup"]["started_at"])
        self.assertIsNotNone(payload["warmup"]["completed_at"])
        self.assertIn("hint", payload["warmup"]["roles"])

    def test_health_degrades_when_warmup_errors(self):
        with mock.patch.dict(os.environ, {"DALI_HEAVY_NODE_DISABLE_STARTUP_WARMUP": "0"}, clear=False):
            with TestClient(create_app(router=FailingWarmupRouter())) as client:
                payload = self._await_warmup(client)
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["warmup"]["status"], "error")
        self.assertIn("warmup exploded", payload["warmup"]["error"])


if __name__ == "__main__":
    unittest.main()
