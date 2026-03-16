from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schemas import TaskType


class ModelRouter:
    def __init__(self, registry_path: Path) -> None:
        with registry_path.open("r", encoding="utf-8") as f:
            self.registry = yaml.safe_load(f)

    def select_role(self, task_type: TaskType) -> str:
        if task_type == TaskType.CODE:
            return "coder"
        if task_type == TaskType.REASONING:
            return "critic"
        return "controller"

    def select_model(self, role: str) -> dict[str, Any]:
        candidates = self.registry["models"][role]["candidates"]
        return max(candidates, key=lambda c: c.get("role_weight", 0.0))
