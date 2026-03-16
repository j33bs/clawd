"""HMBEA Model Router"""
import yaml
from pathlib import Path
from .schemas import Role, TaskType


class ModelRouter:
    """Routes tasks to appropriate roles and models."""
    
    def __init__(self, registry_path: Path):
        with open(registry_path) as f:
            self.registry = yaml.safe_load(f)
    
    def select_role(self, task_type: TaskType) -> Role:
        """Select role based on task type."""
        mapping = {
            TaskType.CODE: Role.CODER,
            TaskType.RESEARCH: Role.CONTROLLER,
            TaskType.CREATIVE: Role.CONTROLLER,
            TaskType.GENERAL: Role.CONTROLLER,
        }
        return mapping.get(task_type, Role.CONTROLLER)
    
    def select_model(self, role: Role) -> dict:
        """Select model for role."""
        role_key = role.value
        candidates = self.registry["models"].get(role_key, {}).get("candidates", [])
        if candidates:
            return candidates[0]
        return {"name": "unknown"}
