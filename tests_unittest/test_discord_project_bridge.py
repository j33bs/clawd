import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api.discord_bridge import bridge_payload, post_bridge_webhooks, render_bridge_state  # noqa: E402


class TestDiscordProjectBridge(unittest.TestCase):
    def test_bridge_payload_renders_channel_previews(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "discord_bridge.json"
            config_path.write_text(
                json.dumps(
                    {
                        "enabled": False,
                        "dry_run": True,
                        "channels": [
                            {
                                "id": "ops_status",
                                "label": "#ops-status",
                                "enabled": True,
                                "delivery": "webhook",
                                "webhook_env": "MISSING_WEBHOOK",
                            },
                            {
                                "id": "project_intake",
                                "label": "#project-intake",
                                "enabled": True,
                                "delivery": "webhook",
                                "webhook_env": "MISSING_WEBHOOK",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            portfolio = {
                "generated_at": "2026-03-10T05:00:00Z",
                "components": [{"name": "Assistant LLM", "status": "healthy", "details": "openclaw-vllm.service active"}],
                "work_items": [{"title": "ITC Cycle", "status": "running", "detail": "classify"}],
                "sims": [],
                "projects": [{"name": "Financial Analysis Pipeline", "status": "active"}],
            }
            tasks = [
                {
                    "id": 42,
                    "title": "Trace SIM_F halt path",
                    "status": "backlog",
                    "priority": "high",
                    "assignee": "coder",
                    "project": "financial-analysis",
                }
            ]

            payload = bridge_payload(portfolio, tasks, config_path=config_path)

            self.assertEqual(payload["status"], "dry_run")
            self.assertEqual(payload["channel_count"], 2)
            self.assertFalse(payload["channels"][0]["has_webhook"])
            self.assertEqual(payload["channels"][0]["boundary"]["items"][1]["label"], "preview only")
            self.assertIn("Assistant LLM", payload["channels"][0]["preview"])
            self.assertIn("Trace SIM_F halt path", payload["channels"][1]["preview"])

    def test_render_bridge_state_writes_atomic_json(self):
        with tempfile.TemporaryDirectory() as td:
            status_path = Path(td) / "bridge_status.json"
            payload = render_bridge_state(
                {
                    "generated_at": "2026-03-10T05:00:00Z",
                    "components": [],
                    "work_items": [],
                    "sims": [],
                    "projects": [],
                },
                [],
                status_path=status_path,
            )

            self.assertTrue(status_path.exists())
            stored = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["rendered_at"], payload["rendered_at"])
            self.assertIn("channels", stored)

    def test_post_bridge_webhooks_skips_unchanged_previews(self):
        with tempfile.TemporaryDirectory() as td:
            status_path = Path(td) / "bridge_status.json"
            payload = {
                "channels": [
                    {
                        "id": "ops_status",
                        "enabled": True,
                        "webhook_env": "TEST_WEBHOOK",
                        "preview": "**Ops Status**\n- healthy",
                        "preview_hash": "abc123",
                    }
                ]
            }

            calls = []

            class _Response:
                status = 204

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            def _fake_urlopen(req, timeout=10):
                calls.append((req.full_url, timeout))
                return _Response()

            with mock.patch.dict("os.environ", {"TEST_WEBHOOK": "https://discord.com/api/webhooks/1/2"}, clear=False):
                with mock.patch("api.discord_bridge.request.urlopen", side_effect=_fake_urlopen):
                    first = post_bridge_webhooks(dict(payload), status_path=status_path)
                    second = post_bridge_webhooks(dict(payload), status_path=status_path)

            self.assertEqual(first[0]["status"], "sent")
            self.assertEqual(second[0]["status"], "unchanged")
            self.assertEqual(len(calls), 1)

    def test_sim_watch_preview_uses_transitions_against_last_sent_state(self):
        with tempfile.TemporaryDirectory() as td:
            status_path = Path(td) / "bridge_status.json"
            config_path = Path(td) / "discord_bridge.json"
            config_path.write_text(
                json.dumps(
                    {
                        "enabled": False,
                        "dry_run": True,
                        "channels": [
                            {
                                "id": "sim_watch",
                                "label": "#sim-watch",
                                "enabled": True,
                                "delivery": "webhook",
                                "webhook_env": "TEST_WEBHOOK",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            previous_state = {
                "last_delivery": {
                    "attempted_at": "2026-03-11T10:00:00Z",
                    "channels": {
                        "sim_watch": {
                            "id": "sim_watch",
                            "status": "sent",
                            "preview_hash": "oldhash",
                            "sent_at": "2026-03-11T10:00:00Z",
                            "state": {
                                "sims": {
                                    "SIM_G": {
                                        "display_name": "CBP Funding Carry",
                                        "bucket": "CBP",
                                        "status": "warning",
                                        "halted": False,
                                        "fee_drag": False,
                                        "open_positions": 0,
                                        "round_trips": 4,
                                        "win_rate": 50.0,
                                        "net_return_pct": -0.1,
                                        "stale": False,
                                    }
                                },
                                "finance": {
                                    "BTCUSDT": {
                                        "action": "hold",
                                        "risk_state": "normal",
                                        "bias": 0.01,
                                        "confidence": 0.62,
                                    }
                                },
                                "feeds": {
                                    "macbook_status": "ok",
                                    "fingpt_status": "ok",
                                    "sentiment_model": "phi4-mini:latest",
                                },
                            },
                        }
                    },
                }
            }
            status_path.write_text(json.dumps(previous_state), encoding="utf-8")

            portfolio = {
                "generated_at": "2026-03-11T11:00:00Z",
                "components": [],
                "work_items": [],
                "projects": [],
                "sims": [
                    {
                        "id": "SIM_G",
                        "display_name": "CBP Funding Carry",
                        "bucket": "CBP",
                        "active_book": True,
                        "status": "warning",
                        "initial_capital": 1000.0,
                        "net_equity_change": -2.81,
                        "net_return_pct": -0.28,
                        "final_equity": 997.19,
                        "mark_equity": 998.04,
                        "live_equity": 998.04,
                        "live_equity_change": -1.96,
                        "live_return_pct": -0.2,
                        "unrealized_pnl": 0.85,
                        "fees_usd": 3.42,
                        "round_trips": 4,
                        "win_rate": 0.0,
                        "fee_drag": False,
                        "halted": False,
                        "open_positions": 1,
                        "updated_at": "2026-03-11T11:00:00Z",
                    }
                ],
                "finance_brain": {
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "action": "flat",
                            "bias": -0.12,
                            "confidence": 0.7,
                            "risk_state": "normal",
                        }
                    ],
                    "external_signal": {
                        "inputs": {
                            "macbook_sentiment": {"status": "ok", "model_resolved": "phi4-mini:latest"},
                            "fingpt_sentiment": {"status": "missing"},
                        }
                    },
                },
            }
            payload = bridge_payload(
                portfolio,
                [],
                config_path=config_path,
                previous_channels=previous_state["last_delivery"]["channels"],
            )

            sim_watch = next(channel for channel in payload["channels"] if channel["id"] == "sim_watch")
            self.assertIn("Active book: 1 sims | 4 trades | live capital $998.04 | live P/L -$1.96 (-0.20%) | booked -$2.81 | 1 open", sim_watch["preview"])
            self.assertIn("CBP Funding Carry: capital $998.04 | P/L -$1.96 (-0.20%) | trades 4 | win 0.0% | 1 open", sim_watch["preview"])
            self.assertIn("open positions 0 -> 1", sim_watch["preview"])
            self.assertIn("win-rate degraded", sim_watch["preview"])
            self.assertIn("BTCUSDT: action hold -> flat", sim_watch["preview"])
            self.assertIn("Dali fallback feed: ok -> missing", sim_watch["preview"])

    def test_post_bridge_webhooks_resends_when_new_schedule_slot_is_due(self):
        with tempfile.TemporaryDirectory() as td:
            status_path = Path(td) / "bridge_status.json"
            payload = {
                "channels": [
                    {
                        "id": "sim_watch",
                        "enabled": True,
                        "webhook_env": "TEST_WEBHOOK",
                        "preview": "**Sim Watch**\n- Active book: 3 strategies, 0 halted, 0 flagged",
                        "preview_hash": "samehash",
                        "schedule_timezone": "Australia/Brisbane",
                        "schedule_local_times": ["09:00", "21:00"],
                    }
                ]
            }
            status_path.write_text(
                json.dumps(
                    {
                        "last_delivery": {
                            "attempted_at": "2026-03-11T00:00:00Z",
                            "channels": {
                                "sim_watch": {
                                    "id": "sim_watch",
                                    "status": "sent",
                                    "preview_hash": "samehash",
                                    "sent_at": "2026-03-11T00:00:00Z",
                                    "sent_slot_id": "2026-03-11@09:00",
                                    "state": {},
                                }
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            calls = []

            class _Response:
                status = 204

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            def _fake_urlopen(req, timeout=10):
                calls.append((req.full_url, timeout))
                return _Response()

            with mock.patch.dict("os.environ", {"TEST_WEBHOOK": "https://discord.com/api/webhooks/1/2"}, clear=False):
                with mock.patch("api.discord_bridge.request.urlopen", side_effect=_fake_urlopen):
                    with mock.patch(
                        "api.discord_bridge._current_schedule_slot",
                        return_value={
                            "slot_id": "2026-03-11@21:00",
                            "slot_label": "21:00",
                            "slot_ts": "2026-03-11T21:00:00+10:00",
                            "timezone": "Australia/Brisbane",
                        },
                    ):
                        result = post_bridge_webhooks(dict(payload), status_path=status_path)

            self.assertEqual(result[0]["status"], "sent")
            self.assertEqual(result[0]["sent_slot_id"], "2026-03-11@21:00")
            self.assertEqual(len(calls), 1)

    def test_post_bridge_webhooks_resends_when_preview_changes_within_same_schedule_slot(self):
        with tempfile.TemporaryDirectory() as td:
            status_path = Path(td) / "bridge_status.json"
            payload = {
                "channels": [
                    {
                        "id": "sim_watch",
                        "enabled": True,
                        "webhook_env": "TEST_WEBHOOK",
                        "preview": "**Sim Watch**\n- Updated active book summary",
                        "preview_hash": "newhash",
                        "schedule_timezone": "Australia/Brisbane",
                        "schedule_local_times": ["21:00"],
                        "min_resend_minutes": 0,
                    }
                ]
            }
            status_path.write_text(
                json.dumps(
                    {
                        "last_delivery": {
                            "attempted_at": "2026-03-15T11:00:04Z",
                            "channels": {
                                "sim_watch": {
                                    "id": "sim_watch",
                                    "status": "sent",
                                    "preview_hash": "oldhash",
                                    "sent_at": "2026-03-15T11:00:04Z",
                                    "sent_slot_id": "2026-03-15@21:00",
                                    "state": {},
                                }
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            calls = []

            class _Response:
                status = 204

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            def _fake_urlopen(req, timeout=10):
                calls.append((req.full_url, timeout))
                return _Response()

            with mock.patch.dict("os.environ", {"TEST_WEBHOOK": "https://discord.com/api/webhooks/1/2"}, clear=False):
                with mock.patch("api.discord_bridge.request.urlopen", side_effect=_fake_urlopen):
                    with mock.patch(
                        "api.discord_bridge._current_schedule_slot",
                        return_value={
                            "slot_id": "2026-03-15@21:00",
                            "slot_label": "21:00",
                            "slot_ts": "2026-03-15T21:00:00+10:00",
                            "timezone": "Australia/Brisbane",
                        },
                    ):
                        result = post_bridge_webhooks(dict(payload), status_path=status_path)

            self.assertEqual(result[0]["status"], "sent")
            self.assertEqual(result[0]["sent_slot_id"], "2026-03-15@21:00")
            self.assertEqual(result[0]["preview_hash"], "newhash")
            self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
