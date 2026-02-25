from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List

try:
    from ._common import memory_ext_enabled, runtime_dir
except ImportError:  # pragma: no cover
    from _common import memory_ext_enabled, runtime_dir


def _tailscale_enabled() -> bool:
    return str(os.getenv("OPENCLAW_TAILSCALE", "0")).strip() == "1"


@dataclass
class MeshNode:
    node_id: str

    def ping(self, node: str) -> Dict[str, Any]:
        if not _tailscale_enabled():
            return {"ok": False, "reason": "tailscale_disabled", "node": node}
        return {"ok": True, "node": node}

    def send_message(self, node: str, msg: str) -> Dict[str, Any]:
        if not _tailscale_enabled():
            return {"ok": False, "reason": "tailscale_disabled", "node": node, "message": msg}
        return {"ok": True, "node": node, "message": msg}

    def relay_via(self, node: str, msg: str) -> Dict[str, Any]:
        if not _tailscale_enabled():
            return {"ok": False, "reason": "tailscale_disabled", "via": node, "message": msg}
        return {"ok": True, "via": node, "message": msg}


def discover_agents() -> List[Dict[str, Any]]:
    if not _tailscale_enabled():
        return []
    exe = shutil.which("tailscale")
    if not exe:
        return []
    try:
        proc = subprocess.run([exe, "status", "--json"], capture_output=True, text=True, check=False)
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        return []
    peers = payload.get("Peer", {}) if isinstance(payload, dict) else {}
    out: List[Dict[str, Any]] = []
    if isinstance(peers, dict):
        for peer in peers.values():
            if not isinstance(peer, dict):
                continue
            tail_ips = peer.get("TailscaleIPs") or [""]
            out.append(
                {
                    "ip": tail_ips[0] if isinstance(tail_ips, list) else "",
                    "name": peer.get("HostName") or peer.get("DNSName") or "",
                    "online": bool(peer.get("Online", False)),
                }
            )
    out.sort(key=lambda x: (not bool(x.get("online")), str(x.get("name", ""))))
    if memory_ext_enabled():
        status_path = runtime_dir("memory_ext", "tailscale_status.json")
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps({"agents": out}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def mesh_broadcast(message: str, ttl: int = 3) -> Dict[str, Any]:
    if not _tailscale_enabled():
        return {"delivered_to": [], "failed": [], "ttl": ttl, "status": "disabled"}
    agents = discover_agents()
    delivered = [a.get("name", "") for a in agents if a.get("online")]
    failed = [a.get("name", "") for a in agents if not a.get("online")]
    return {"delivered_to": delivered, "failed": failed, "ttl": int(ttl), "message": message}


def relay_to_agent(target_ip: str, message: str) -> Dict[str, Any]:
    if not _tailscale_enabled():
        return {"ok": False, "reason": "tailscale_disabled", "target_ip": target_ip}
    return {"ok": True, "target_ip": target_ip, "message": message}


__all__ = ["MeshNode", "discover_agents", "mesh_broadcast", "relay_to_agent"]
