from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class MCPorterError(RuntimeError):
    pass


class MCPorterAdapter:
    """Optional MCPorter bridge with deny-by-default allowlist."""

    def __init__(self, repo_root: Path, config_path: Path | None = None) -> None:
        self.repo_root = repo_root
        self.config_path = config_path or (repo_root / "config" / "mcporter.json")
        self._cfg = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {"enabled_tools": [], "timeout_sec": 30, "max_response_bytes": 131072}
        try:
            parsed = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MCPorterError(f"invalid_mcporter_config:{exc}") from exc

        enabled = parsed.get("enabled_tools", [])
        if not isinstance(enabled, list) or not all(isinstance(name, str) for name in enabled):
            raise MCPorterError("invalid_mcporter_config:enabled_tools")
        timeout_sec = int(parsed.get("timeout_sec", 30))
        max_response_bytes = int(parsed.get("max_response_bytes", 131072))
        return {
            "enabled_tools": enabled,
            "timeout_sec": max(1, min(timeout_sec, 300)),
            "max_response_bytes": max(1024, min(max_response_bytes, 1048576)),
        }

    @property
    def enabled_tools(self) -> set[str]:
        return set(self._cfg.get("enabled_tools", []))

    @staticmethod
    def command_path() -> str | None:
        return shutil.which("mcporter")

    def is_available(self) -> bool:
        return self.command_path() is not None

    def list_tools(self) -> dict[str, Any]:
        if not self.is_available():
            return {"available": False, "blocked_by": "mcporter_not_installed", "tools": []}

        argv = [self.command_path(), "list-tools", "--json"]
        proc = subprocess.run(argv, cwd=str(self.repo_root), capture_output=True, text=True, timeout=self._cfg["timeout_sec"], check=False)
        if proc.returncode != 0:
            return {"available": False, "blocked_by": "mcporter_list_failed", "stderr": proc.stderr[:4000], "tools": []}

        payload = (proc.stdout or "")[: self._cfg["max_response_bytes"]]
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = []
        names = [row.get("name") for row in parsed if isinstance(row, dict) and isinstance(row.get("name"), str)]
        filtered = [name for name in names if name in self.enabled_tools]
        return {"available": True, "tools": filtered, "allowlist_count": len(self.enabled_tools)}

    def call_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self.enabled_tools:
            raise MCPorterError(f"tool_not_allowed:{tool_name}")
        if not self.is_available():
            raise MCPorterError("blocked_by:mcporter_not_installed")
        if not isinstance(payload, dict):
            raise MCPorterError("payload_must_be_object")

        argv = [self.command_path(), "call", tool_name, "--json", json.dumps(payload, ensure_ascii=False)]
        proc = subprocess.run(argv, cwd=str(self.repo_root), capture_output=True, text=True, timeout=self._cfg["timeout_sec"], check=False)

        stdout = (proc.stdout or "")[: self._cfg["max_response_bytes"]]
        stderr = (proc.stderr or "")[: self._cfg["max_response_bytes"]]
        result: dict[str, Any] = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
        if proc.returncode != 0:
            raise MCPorterError(f"mcporter_call_failed:{tool_name}")
        return result
