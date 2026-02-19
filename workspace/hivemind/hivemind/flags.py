from __future__ import annotations

import os
from typing import Iterable, Mapping


TRUTHY_VALUES = {"1", "true", "yes", "on"}

TACTI_DYNAMICS_FLAGS = (
    "ENABLE_MURMURATION",
    "ENABLE_RESERVOIR",
    "ENABLE_PHYSARUM_ROUTER",
    "ENABLE_TRAIL_MEMORY",
)


def is_enabled(name: str, environ: Mapping[str, str] | None = None) -> bool:
    env = environ or os.environ
    value = str(env.get(name, "0")).strip().lower()
    return value in TRUTHY_VALUES


def any_enabled(names: Iterable[str], environ: Mapping[str, str] | None = None) -> bool:
    return any(is_enabled(name, environ=environ) for name in names)


def enabled_map(names: Iterable[str], environ: Mapping[str, str] | None = None) -> dict[str, bool]:
    return {str(name): is_enabled(str(name), environ=environ) for name in names}
