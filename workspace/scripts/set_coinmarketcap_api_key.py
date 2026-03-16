#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HOME_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_REPO_CONFIG = REPO_ROOT / ".openclaw" / "openclaw.json"
DEFAULT_MARKET_CONFIG = REPO_ROOT / "workspace" / "config" / "market_sentiment_sources.json"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _backup(path: Path) -> Path:
    backup_path = path.with_name(f"{path.name}.bak.{_utc_stamp()}")
    backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def _update_openclaw_env(path: Path, key: str) -> Path:
    payload = _load_json(path)
    env = payload.setdefault("env", {})
    env_vars = env.setdefault("vars", {})
    if not isinstance(env_vars, dict):
        raise ValueError(f"invalid_env_vars:{path}")
    backup_path = _backup(path)
    env_vars["COINMARKETCAP_API_KEY"] = key
    _write_json(path, payload)
    return backup_path


def _update_market_config(path: Path) -> tuple[Path, str]:
    payload = _load_json(path)
    source_cfg = ((payload.get("sources") or {}).get("coinmarketcap")) or {}
    if not isinstance(source_cfg, dict):
        raise ValueError("invalid_coinmarketcap_source_config")
    backup_path = _backup(path)
    source_cfg["api_key_env"] = "COINMARKETCAP_API_KEY"
    source_cfg["base_url"] = "https://pro-api.coinmarketcap.com"
    _write_json(path, payload)
    return backup_path, str(source_cfg.get("base_url") or "")


def _test_key(*, base_url: str, key: str, timeout_seconds: int = 10) -> int:
    response = requests.get(
        f"{base_url.rstrip('/')}/v1/key/info",
        headers={"Accept": "application/json", "X-CMC_PRO_API_KEY": key},
        timeout=timeout_seconds,
    )
    return response.status_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Store a CoinMarketCap API key in local OpenClaw config.")
    parser.add_argument("--key", help="CoinMarketCap API key. If omitted, prompts securely.")
    parser.add_argument("--skip-test", action="store_true", help="Skip key validation after writing config.")
    parser.add_argument("--home-config", default=str(DEFAULT_HOME_CONFIG))
    parser.add_argument("--repo-config", default=str(DEFAULT_REPO_CONFIG))
    parser.add_argument("--market-config", default=str(DEFAULT_MARKET_CONFIG))
    args = parser.parse_args()

    key = args.key or getpass.getpass("CoinMarketCap API key: ").strip()
    if not key:
        raise SystemExit("empty_api_key")

    home_config = Path(args.home_config).expanduser()
    repo_config = Path(args.repo_config).expanduser()
    market_config = Path(args.market_config).expanduser()

    for path in (home_config, repo_config, market_config):
        if not path.is_file():
            raise SystemExit(f"missing_config:{path}")

    home_backup = _update_openclaw_env(home_config, key)
    repo_backup = _update_openclaw_env(repo_config, key)
    market_backup, base_url = _update_market_config(market_config)

    print(f"updated={home_config}")
    print(f"backup={home_backup}")
    print(f"updated={repo_config}")
    print(f"backup={repo_backup}")
    print(f"updated={market_config}")
    print(f"backup={market_backup}")
    print(f"coinmarketcap_base_url={base_url}")

    if args.skip_test:
        print("test=skipped")
        return 0

    status_code = _test_key(base_url=base_url, key=key)
    print(f"ping_status={status_code}")
    return 0 if 200 <= status_code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
