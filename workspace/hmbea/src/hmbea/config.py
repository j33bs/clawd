"""HMBEA Configuration"""
import os


def get_settings():
    return Settings()


class Settings:
    def __init__(self):
        # Paths relative to repo root
        self.registry_path = "workspace/hmbea/configs/model_registry.yaml"
        self.escalation_policy_path = "workspace/hmbea/policies/escalation_policy.yaml"
        self.tool_policy_path = "workspace/hmbea/policies/tool_policy.yaml"
        
        # Local LLM (Qwen 3.5 27B on llama.cpp)
        self.controller_base_url = os.environ.get("HMBEA_CONTROLLER_URL", "http://localhost:8001/v1")
        self.controller_model = os.environ.get("HMBEA_CONTROLLER_MODEL", "local-assistant")
        
        # All roles use same model for now (single GPU)
        self.specialist_base_url = self.controller_base_url
        self.specialist_model = self.controller_model
        self.critic_base_url = self.controller_base_url
        self.critic_model = self.controller_model
