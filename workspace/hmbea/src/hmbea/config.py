"""HMBEA Configuration"""
import os
from pathlib import Path
from functools import lru_cache


@lru_cache()
def get_settings():
    """Get HMBEA settings from environment."""
    return Settings()


class Settings:
    def __init__(self):
        self.registry_path = Path(os.environ.get("HMBEA_REGISTRY_PATH", "workspace/hmbea/configs/model_registry.yaml"))
        self.escalation_policy_path = Path(os.environ.get("HMBEA_ESCALATION_PATH", "workspace/hmbea/policies/escalation_policy.yaml"))
        self.tool_policy_path = Path(os.environ.get("HMBEA_TOOL_PATH", "workspace/hmbea/policies/tool_policy.yaml"))
        
        # Default to local llama.cpp server
        self.controller_base_url = os.environ.get("HMBEA_CONTROLLER_URL", "http://localhost:8001/v1")
        self.controller_model = os.environ.get("HMBEA_CONTROLLER_MODEL", "qwen3-14b")
        self.specialist_base_url = os.environ.get("HMBEA_SPECIALIST_URL", "http://localhost:8001/v1")
        self.specialist_model = os.environ.get("HMBEA_SPECIALIST_MODEL", "qwen3-coder-next")
        self.critic_base_url = os.environ.get("HMBEA_CRITIC_URL", "http://localhost:8001/v1")
        self.critic_model = os.environ.get("HMBEA_CRITIC_MODEL", "phi-4-mini-flash-reasoning")
