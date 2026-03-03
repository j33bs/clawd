from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class BudgetLimits:
    max_wall_time_sec: int
    max_tool_calls: int
    max_output_bytes: int
    max_concurrency_slots: int


class BudgetTracker:
    def __init__(self, limits: BudgetLimits) -> None:
        self.limits = limits
        self.started = time.monotonic()
        self.tool_calls = 0
        self.output_bytes = 0

    def elapsed_sec(self) -> float:
        return time.monotonic() - self.started

    def check_wall_time(self) -> None:
        if self.elapsed_sec() > float(self.limits.max_wall_time_sec):
            raise BudgetExceeded("max_wall_time_sec exceeded")

    def record_tool_call(self, count: int = 1) -> None:
        self.tool_calls += count
        if self.tool_calls > self.limits.max_tool_calls:
            raise BudgetExceeded("max_tool_calls exceeded")

    def record_output_bytes(self, count: int) -> None:
        self.output_bytes += count
        if self.output_bytes > self.limits.max_output_bytes:
            raise BudgetExceeded("max_output_bytes exceeded")


def kill_switch_path(repo_root: Path) -> Path:
    return repo_root / "workspace" / "local_exec" / "state" / "KILL_SWITCH"


def kill_switch_enabled(repo_root: Path) -> bool:
    return kill_switch_path(repo_root).exists()
