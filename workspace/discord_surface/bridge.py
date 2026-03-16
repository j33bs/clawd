from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import requests

from .store import default_bridge_state_doc, read_json, utc_now_iso, write_atomic_json


def payload_hash(content: str) -> str:
    return hashlib.sha256(str(content).encode("utf-8")).hexdigest()


def load_delivery_state(path: Path) -> dict[str, Any]:
    return read_json(path, default_bridge_state_doc())


def should_skip_delivery(state: dict[str, Any], delivery_key: str, content: str) -> bool:
    deliveries = state.get("deliveries") or {}
    previous = deliveries.get(delivery_key) or {}
    return previous.get("hash") == payload_hash(content)


def record_delivery(path: Path, state: dict[str, Any], delivery_key: str, content: str, *, status: str) -> None:
    deliveries = state.setdefault("deliveries", {})
    deliveries[delivery_key] = {
        "hash": payload_hash(content),
        "status": status,
        "updated_at": utc_now_iso(),
    }
    state["updated_at"] = utc_now_iso()
    write_atomic_json(path, state)


def post_webhook(url: str, content: str) -> requests.Response:
    return requests.post(
        url,
        json={"content": content, "allowed_mentions": {"parse": []}},
        timeout=15,
    )

