from __future__ import annotations

import threading
import time
import weakref
from typing import Any, Dict, List, Tuple

_CACHE_LOCK = threading.Lock()
_STORE_CACHE: "weakref.WeakKeyDictionary[Any, Dict[str, Any]]" = weakref.WeakKeyDictionary()


def get_all_units_cached(store: Any, ttl_seconds: float = 60.0) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    ttl = max(0.0, float(ttl_seconds))
    now = time.monotonic()
    with _CACHE_LOCK:
        entry = _STORE_CACHE.get(store)
        if entry and (now - float(entry.get("loaded_at", 0.0))) <= ttl:
            units = [dict(row) for row in entry.get("units", [])]
            return units, {"cache_hit": True, "count": len(units), "ttl_seconds": ttl}

    if hasattr(store, "all_units_cached"):
        units = list(store.all_units_cached(ttl_seconds=ttl))
    else:
        units = list(store.all_units())

    with _CACHE_LOCK:
        _STORE_CACHE[store] = {"loaded_at": now, "units": [dict(row) for row in units]}
    return [dict(row) for row in units], {"cache_hit": False, "count": len(units), "ttl_seconds": ttl}


def invalidate_all_units_cached(store: Any) -> None:
    with _CACHE_LOCK:
        _STORE_CACHE.pop(store, None)
