import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api import portfolio  # noqa: E402


class PortfolioPayloadTests(unittest.TestCase):
    def test_load_trading_strategy_extracts_report_and_alignment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report_path = root / "openclaw_trading_strategy_report_v2.md"
            report_path.write_text(
                """# OpenClaw Trading System Strategy Report

## Executive Summary

### Recommended live scope

1. **Alpaca US equities/ETFs/news**
2. **Kraken spot crypto**

### Supported but not initially live

3. **Hyperliquid adapter**

### Explicitly excluded for Australia

4. **Kalshi** — do not deploy.
5. **Polymarket** — do not deploy.

## Hard portfolio limits

- **No leverage** in production phase 1.
- **Max gross exposure:** 85% NAV
- **Max open positions:** 3

## Strategy 1 — US Equity Event Impulse (UEEI)
## Strategy 2 — ETF Narrative Spillover (ETNS)

## What Another Model Should Do Next in the Repo

1. Create the repo skeleton above.
2. Implement the common schemas first.
3. Build collectors before strategies.
""",
                encoding="utf-8",
            )
            base_cfg = root / "base.yaml"
            live_cfg = root / "live.au.yaml"
            base_cfg.write_text("mode: paper\n", encoding="utf-8")
            live_cfg.write_text("mode: live\n", encoding="utf-8")

            pipeline_snapshot = {
                "status": "active",
                "enabled_sims": [
                    {
                        "id": "SIM_G",
                        "display_name": "CBP Funding Carry",
                        "strategy": "perp_funding_carry",
                        "universe": ["BTCUSDT", "ETHUSDT"],
                    },
                    {
                        "id": "SIM_H",
                        "display_name": "LOAR Consensus",
                        "strategy": "latency_consensus_long_flat",
                        "universe": ["BTCUSDT"],
                    },
                ],
                "enabled_universe": ["BTCUSDT", "ETHUSDT"],
                "path": str(root / "system1_trading.yaml"),
            }

            with (
                patch.object(portfolio, "TRADING_STRATEGY_REPORT_PATHS", (report_path,)),
                patch.object(portfolio, "TRADING_BLUEPRINT_CONFIGS", (base_cfg, live_cfg)),
                patch.object(portfolio, "_load_trading_pipeline_snapshot", return_value=pipeline_snapshot),
            ):
                payload = portfolio._load_trading_strategy()

            self.assertEqual(payload["status"], "active")
            self.assertEqual(payload["title"], "OpenClaw Trading System Strategy Report")
            self.assertIn("Alpaca US equities/ETFs/news", payload["live_scope"])
            self.assertIn("Kraken spot crypto", payload["live_scope"])
            self.assertIn("Hyperliquid adapter", payload["research_scope"])
            self.assertIn("Kalshi — do not deploy.", payload["excluded_scope"])
            self.assertIn("US Equity Event Impulse (UEEI)", payload["strategy_stack"][0])
            self.assertEqual(payload["integration"]["status"], "misaligned")
            self.assertTrue(any(row["status"] == "blocked" for row in payload["integration"]["enabled_sims"]))
            self.assertTrue(all(item["exists"] for item in payload["config_paths"]))

    def test_load_source_mission_returns_machine_readable_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mission_path = root / "source_mission.json"
            mission_path.write_text(
                json.dumps(
                    {
                        "statement": "Build a collective intelligence surface.",
                        "tagline": "Shared command and memory.",
                        "north_star": "Make coordination compounding.",
                        "operating_commitments": [
                            "Keep provenance visible.",
                            "Distill evidence into useful memory.",
                        ],
                        "pillars": [
                            {"id": "think", "label": "Think", "summary": "Shared context."},
                            {"id": "remember", "label": "Remember", "summary": "Durable memory."},
                        ],
                        "tasks": [
                            {
                                "id": "source-001",
                                "title": "Universal Context Packet",
                                "pillar": "think",
                                "priority": "critical",
                                "summary": "One packet everywhere.",
                                "definition_of_done": "Every surface sees the same packet.",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch.object(portfolio, "SOURCE_MISSION_PATH", mission_path):
                payload = portfolio._load_source_mission(
                    tasks=[{"status": "backlog"}, {"status": "in_progress"}],
                    memory_ops={"totals": {"rows": 9}},
                    model_ops={"summary": {"distinct_models": 3}},
                    work_items=[{"id": "job-1"}],
                    teamchat={"active_count": 2},
                    context_packet={"summary_lines": ["Open work 2"]},
                )

            self.assertEqual(payload["status"], "active")
            self.assertEqual(payload["tasks"][0]["pillar_label"], "Think")
            self.assertEqual(payload["signals"][1]["value"], "4")
            self.assertEqual(payload["signals"][2]["value"], "9")
            self.assertEqual(payload["signals"][3]["value"], "3")
            self.assertEqual(payload["signals"][4]["value"], "3")
            self.assertIn("pillars", payload["summary"])

    def test_load_memory_ops_summarizes_sources_and_inferences(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            discord_path = root / "discord.jsonl"
            research_path = root / "research.jsonl"
            telegram_path = root / "telegram.jsonl"
            inferences_path = root / "inferences.jsonl"
            profile_path = root / "profile.json"

            discord_path.write_text(
                json.dumps(
                    {
                        "stored_at": "2026-03-12T00:00:00Z",
                        "role": "user",
                        "content": "discord note",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            research_path.write_text(
                json.dumps(
                    {
                        "stored_at": "2026-03-12T00:01:00Z",
                        "message_id": "1481282624508133549",
                        "role": "user",
                        "content": "research thread",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            telegram_path.write_text(
                json.dumps(
                    {
                        "stored_at": "2026-03-12T00:02:00Z",
                        "role": "user",
                        "content": "telegram note",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            inferences_path.write_text(
                json.dumps(
                    {
                        "id": "ui_x",
                        "status": "active",
                        "statement": "Prefers concise summaries.",
                        "confidence": 0.9,
                        "profile_section": "communication",
                        "review_state": "auto_distilled",
                        "prompt_line": "Prefer concise summaries.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            profile_path.write_text(
                json.dumps({"updated_at": "2026-03-12T00:03:00Z"}, indent=2),
                encoding="utf-8",
            )

            with (
                patch.object(portfolio, "DISCORD_MEMORY_PATH", discord_path),
                patch.object(portfolio, "DISCORD_RESEARCH_PATH", research_path),
                patch.object(portfolio, "TELEGRAM_MEMORY_PATH", telegram_path),
                patch.object(portfolio, "USER_INFERENCES_PATH", inferences_path),
                patch.object(portfolio, "PREFERENCE_PROFILE_PATH", profile_path),
            ):
                payload = portfolio._load_memory_ops(tasks=[])

            self.assertEqual(payload["totals"]["rows"], 3)
            self.assertEqual(payload["totals"]["inferences"], 1)
            self.assertEqual(payload["sources"][0]["count"], 1)
            self.assertEqual(payload["sources"][0]["boundary"]["items"][1]["label"], "raw memory only")
            self.assertIn("research thread", payload["research_topics"][0])
            self.assertEqual(payload["research_items"][0]["id"], "1481282624508133549")
            self.assertEqual(payload["research_items"][0]["source_links"][0]["href"], "/api/research/items/1481282624508133549")
            self.assertEqual(payload["research_boundary"]["items"][1]["label"], "review before share")
            self.assertEqual(payload["active_inferences"][0]["profile_section"], "communication")
            self.assertEqual(payload["active_inferences"][0]["boundary"]["items"][1]["label"], "review before share")
            self.assertEqual(payload["preference_profile"]["boundary"]["items"][1]["label"], "mixed review state")

    def test_load_sim_ops_partitions_active_and_frozen(self):
        sims = [
            {
                "id": "SIM_E",
                "display_name": "CBP Reversion Grid",
                "bucket": "CBP",
                "active_book": True,
                "initial_capital": 1000.0,
                "net_equity_change": -12.0,
                "net_return_pct": -1.2,
                "final_equity": 988.0,
                "mark_equity": 992.5,
                "live_equity": 992.5,
                "live_equity_change": -7.5,
                "live_return_pct": -0.75,
                "unrealized_pnl": 4.5,
                "fees_usd": 3.4,
                "win_rate": 41.0,
                "round_trips": 52,
                "open_positions": 1,
                "avg_hold_hours": 1.5,
                "fee_drag": True,
                "halted": False,
                "status_note": "Primary low-latency candidate",
                "updated_at": "2026-03-12T00:10:00Z",
            },
            {
                "id": "SIM_D",
                "display_name": "Bleeding Edge Tick Scalper",
                "bucket": "Bleeding Edge",
                "active_book": False,
                "net_return_pct": -6.5,
                "status_note": "Frozen pending redesign",
            },
        ]

        payload = portfolio._load_sim_ops(sims)

        self.assertEqual(payload["summary"]["active_count"], 1)
        self.assertEqual(payload["summary"]["growing_count"], 0)
        self.assertEqual(payload["summary"]["frozen_count"], 1)
        self.assertEqual(payload["summary"]["attention_count"], 1)
        self.assertEqual(payload["summary"]["trade_count"], 52)
        self.assertEqual(payload["summary"]["live_equity"], 992.5)
        self.assertEqual(payload["summary"]["live_pnl"], -7.5)
        self.assertIn("fee drag", payload["active"][0]["flags"])
        self.assertEqual(payload["active"][0]["final_equity"], 988.0)
        self.assertEqual(payload["active"][0]["mark_equity"], 992.5)
        self.assertEqual(payload["active"][0]["live_equity_change"], -7.5)
        self.assertEqual(payload["active"][0]["fees_usd"], 3.4)
        self.assertEqual(payload["frozen"][0]["id"], "SIM_D")


if __name__ == "__main__":
    unittest.main()
