from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    controller_base_url: str = os.getenv("HMBEA_CONTROLLER_URL", "http://localhost:8000/v1")
    specialist_base_url: str = os.getenv("HMBEA_SPECIALIST_URL", "http://localhost:8001/v1")
    critic_base_url: str = os.getenv("HMBEA_CRITIC_URL", "http://localhost:8002/v1")
    controller_model: str = os.getenv("HMBEA_CONTROLLER_MODEL", "controller")
    specialist_model: str = os.getenv("HMBEA_SPECIALIST_MODEL", "coder")
    critic_model: str = os.getenv("HMBEA_CRITIC_MODEL", "critic")
    registry_path: Path = Path(os.getenv("HMBEA_REGISTRY_PATH", "configs/model_registry.yaml"))
    escalation_policy_path: Path = Path(os.getenv("HMBEA_ESCALATION_POLICY_PATH", "policies/escalation_policy.yaml"))
    tool_policy_path: Path = Path(os.getenv("HMBEA_TOOL_POLICY_PATH", "policies/tool_policy.yaml"))
    max_retries: int = int(os.getenv("HMBEA_MAX_RETRIES", "1"))


def get_settings() -> Settings:
    return Settings()
