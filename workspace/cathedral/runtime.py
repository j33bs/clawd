from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from .aesthetic_feedback import AestheticFeedbackStore
from .control_bus import ControlBus
from .control_api import load_control_state as load_fishtank_control_state, write_control_state as write_fishtank_control_state
from .curiosity_router import CuriosityRouter
from .fishtank_renderer import FishTankRenderer
from .gpu_lease import GPULease
from .io_utils import append_jsonl, atomic_write_json, clamp01, load_json, utc_now_iso
from .logging_utils import JsonlLogger
from .paths import (
    AESTHETIC_EVENTS_DIR,
    CURIOSITY_LATEST_PATH,
    FISHTANK_STATE_PATH,
    GPU_LEASE_PATH,
    NOVELTY_ARCHIVE_DIR,
    PHASE_ONE_IDLE_STATUS_PATH,
    RUNTIME_LOGS,
    SYSTEM_PHYSIOLOGY_PATH,
    TACTI_STATE_PATH,
    WORKSPACE_ROOT,
    ensure_runtime_dirs,
)
from .tacti_state_ingest import TactiStateIngestor
from .telemetryd import TelemetryDaemon
from .telegram_interface import TelegramCommandInterface

INFERENCE_ACTIVE_PATH = WORKSPACE_ROOT / "runtime" / "inference_active.json"
REPO_ROOT = WORKSPACE_ROOT.parent
PHASE_ONE_FRONTEND_ALIASES = {
    "phase1": "phase1",
    "phase_one": "phase1",
    "phase1_commandlet": "phase1",
    "work": "mirror",
    "work_mode": "mirror",
    "mirror": "mirror",
}

_DALI_FULLSCREEN_TOKENS = (
    "dali",
    "consciousness mirror",
    "cathedral",
    "fishtank",
)


def _x11_probe_env() -> dict[str, str]:
    env = os.environ.copy()
    uid = os.getuid()
    env.setdefault("DISPLAY", str(env.get("DISPLAY") or ":0").strip() or ":0")
    env.setdefault("XDG_RUNTIME_DIR", str(env.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}").strip() or f"/run/user/{uid}")
    env.setdefault(
        "DBUS_SESSION_BUS_ADDRESS",
        str(env.get("DBUS_SESSION_BUS_ADDRESS") or f"unix:path={env['XDG_RUNTIME_DIR']}/bus").strip(),
    )
    xauthority = str(env.get("XAUTHORITY") or (str(Path.home() / ".Xauthority"))).strip()
    if xauthority:
        env["XAUTHORITY"] = xauthority
    return env


def _strip_xprop_value(raw: str) -> str:
    text = str(raw or "").strip()
    if "=" in text:
        text = text.split("=", 1)[1].strip()
    return text.strip().strip('"')


def _window_looks_like_dali(*, title: str, wm_class: str) -> bool:
    combined = f"{title} {wm_class}".strip().lower()
    return any(token in combined for token in _DALI_FULLSCREEN_TOKENS)


def _detect_other_fullscreen_windows() -> tuple[list[dict[str, str]], str]:
    env = _x11_probe_env()
    try:
        active = subprocess.run(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
            env=env,
        )
    except Exception:
        return [], "xprop_active_window_error"
    if active.returncode != 0:
        return [], "xprop_active_window_failed"
    match = re.search(r"(0x[0-9a-fA-F]+)", active.stdout or "")
    if match is None:
        return [], "xprop_no_active_window"
    window_id = match.group(1)
    if window_id.lower() == "0x0":
        return [], "xprop_no_active_window"
    try:
        details = subprocess.run(
            ["xprop", "-id", window_id, "_NET_WM_STATE", "WM_CLASS", "_NET_WM_NAME"],
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
            env=env,
        )
    except Exception:
        return [], "xprop_window_error"
    if details.returncode != 0:
        return [], "xprop_window_failed"
    stdout = details.stdout or ""
    state_line = next((line for line in stdout.splitlines() if line.startswith("_NET_WM_STATE")), "")
    if "_NET_WM_STATE_FULLSCREEN" not in state_line:
        return [], "xprop_active_not_fullscreen"
    title_line = next((line for line in stdout.splitlines() if line.startswith("_NET_WM_NAME")), "")
    wm_class_line = next((line for line in stdout.splitlines() if line.startswith("WM_CLASS")), "")
    title = _strip_xprop_value(title_line)
    wm_class = _strip_xprop_value(wm_class_line)
    if _window_looks_like_dali(title=title, wm_class=wm_class):
        return [], "xprop_own_window"
    return [{"window_id": window_id, "title": title, "wm_class": wm_class}], "xprop_scan"


class DaliCathedralRuntime:
    def __init__(
        self,
        *,
        rate_hz: float = 30.0,
        telemetry_hz: float = 6.0,
        tacti_hz: float = 2.0,
        agent_count: int = 120_000,
        headless: bool = False,
        require_gpu: bool = True,
        telegram_enabled: bool = False,
        telegram_token: str = "",
        telegram_allowlist: list[str] | None = None,
        telegram_autoclear_webhook: bool = False,
        telegram_debug_drain: bool = False,
        telegram_requested: bool = False,
        telegram_missing_keys: list[str] | None = None,
        telegram_env_file: str = "",
        enter_display_mode: bool = False,
    ):
        ensure_runtime_dirs()
        self.rate_hz = max(1.0, float(rate_hz))
        self.stop_event = threading.Event()
        self.log = JsonlLogger(RUNTIME_LOGS / "dali_cathedral_runtime.log")
        self._fatal_error: BaseException | None = None
        self.runtime_instance_id = f"cathedral-{uuid.uuid4().hex[:12]}"
        self.pid = os.getpid()
        self.runtime_start_ts = utc_now_iso()
        self.last_idle_activation_ts = ""

        frontend = str(os.environ.get("DALI_FISHTANK_FRONTEND", "python") or "python").strip().lower()
        frontend = PHASE_ONE_FRONTEND_ALIASES.get(frontend, frontend)
        self.frontend = frontend if frontend in {"python", "ue5", "phase1", "mirror"} else "python"
        self.frontend_fullscreen_requested = str(os.environ.get("DALI_FISHTANK_FULLSCREEN", "1") or "1").strip() != "0"
        default_ue5_launcher = REPO_ROOT / "scripts" / "dali_ue5_run_game.sh"
        default_phase1_launcher = REPO_ROOT / "scripts" / "dali_phase1_idle_run.sh"
        if self.frontend == "ue5":
            frontend_process_path = os.environ.get("DALI_FISHTANK_UE5_LAUNCHER", "") or str(default_ue5_launcher)
        elif self.frontend == "phase1":
            frontend_process_path = os.environ.get("DALI_FISHTANK_PHASE1_LAUNCHER", "") or str(default_phase1_launcher)
        else:
            frontend_process_path = ""
        self.frontend_process_path = str(frontend_process_path).strip()
        self.frontend_run_mode = "persistent" if self.frontend == "ue5" else ("oneshot" if self.frontend == "phase1" else "none")
        self.frontend_process: subprocess.Popen[str] | None = None
        self.frontend_process_running = False
        self.frontend_process_pid = 0
        self.frontend_last_exit_code: int | None = None
        self.frontend_last_exit_ts = ""
        self.frontend_last_start_ts = ""
        self.frontend_last_runtime_s = 0.0
        self.frontend_failure_streak = 0
        self.frontend_restart_backoff_s = 0.0
        self.frontend_next_restart_monotonic = 0.0
        self.frontend_last_start_monotonic = 0.0
        self.frontend_activation_pending = False
        self.frontend_last_status = "idle"
        self.frontend_last_error = ""
        self.frontend_last_manifest_path = ""
        self.frontend_last_output_root = ""
        self.frontend_last_completed_ts = ""
        self.frontend_last_status_payload: dict[str, Any] = {}
        self.frontend_status_path = str(
            os.environ.get("DALI_FISHTANK_PHASE1_STATUS_PATH", "") or (str(PHASE_ONE_IDLE_STATUS_PATH) if self.frontend == "phase1" else "")
        ).strip()
        self._phase1_idle_episode_consumed = False
        self._phase1_requested_mode_on_consumed_ts = ""
        self.phase1_idle_autorun_enabled = str(os.environ.get("DALI_FISHTANK_PHASE1_IDLE_AUTORUN", "0") or "0").strip() == "1"
        self.python_visible_attach_enabled = (
            str(os.environ.get("DALI_FISHTANK_ALLOW_PYTHON_VISIBLE_ATTACH", "0") or "0").strip() == "1"
        )
        self._phase1_idle_autorun_block_log_ts = 0.0
        self._python_visible_attach_block_log_ts = 0.0
        self.frontend_success_reset_s = max(
            3.0,
            float(os.environ.get("DALI_FISHTANK_FRONTEND_SUCCESS_RESET_S", "15") or 15.0),
        )
        self.frontend_restart_cap_s = max(
            5.0,
            float(os.environ.get("DALI_FISHTANK_FRONTEND_RESTART_CAP_S", "60") or 60.0),
        )
        self.frontend_launch_env_summary: dict[str, str] = {}
        self.frontend_log_path = RUNTIME_LOGS / "dali_frontend.log"
        self._frontend_log_handle: Any | None = None
        self._frontend_restart_wait_log_ts = 0.0

        self.telemetry = TelemetryDaemon(rate_hz=telemetry_hz)
        self.tacti_ingest = TactiStateIngestor(rate_hz=tacti_hz)
        self.curiosity = CuriosityRouter()
        self.control_bus = ControlBus()
        self.lease_mode = str(os.environ.get("DALI_FISHTANK_GPU_LEASE_MODE", "exclusive") or "exclusive").strip().lower()
        if self.lease_mode not in {"exclusive", "shared"}:
            self.lease_mode = "exclusive"
        self.lease_ttl_s = max(5.0, float(os.environ.get("DALI_FISHTANK_GPU_LEASE_TTL_S", "20") or 20.0))
        self.lease_owner = f"dali-fishtank:{socket.gethostname()}:{os.getpid()}"
        self.gpu_lease = GPULease(path=GPU_LEASE_PATH)
        self._lease_last_renew_ts = 0.0
        self._lease_acquired = False
        self.quiesce_enabled = str(os.environ.get("DALI_FISHTANK_QUIESCE_INFERENCE", "1") or "1").strip() != "0"
        self.quiesce_endpoint = str(os.environ.get("DALI_FISHTANK_QUIESCE_ENDPOINT", "") or "").strip()
        default_quiesce_units = "openclaw-dali-heavy-node.service" if self.lease_mode == "exclusive" else ""
        self.quiesce_units = [
            item.strip()
            for item in str(os.environ.get("DALI_FISHTANK_QUIESCE_UNITS", default_quiesce_units) or "").split(",")
            if item.strip()
        ]
        self._quiesced_units: list[str] = []
        self.inference_quiesced = False
        self._quiesce_allowlist = {
            "openclaw-vllm.service",
            "openclaw-vllm-coder.service",
            "openclaw-dali-heavy-node.service",
            "openclaw-agent.service",
            "openclaw-heavy-node.service",
            "openclaw-worker.service",
        }

        self.idle_mode_enabled = str(os.environ.get("DALI_FISHTANK_IDLE_ENABLE", "1") or "1").strip() != "0"
        self.idle_seconds = max(5.0, float(os.environ.get("DALI_FISHTANK_IDLE_SECONDS", "300") or 300.0))
        trigger_source = str(os.environ.get("DALI_FISHTANK_IDLE_TRIGGER_SOURCE", "internal") or "internal").strip().lower()
        self.idle_trigger_source = trigger_source if trigger_source in {"internal", "gnome", "manual", "session"} else "internal"
        self.idle_inhibit_enabled = str(os.environ.get("DALI_FISHTANK_IDLE_INHIBIT", "1") or "1").strip() != "0"
        self.abort_if_fullscreen_active = (
            str(os.environ.get("DALI_FISHTANK_ABORT_IF_FULLSCREEN_ACTIVE", "0") or "0").strip() != "0"
        )
        self.fullscreen_guard_probe = "disabled"
        self.fullscreen_guard_blocked = False
        self.fullscreen_guard_windows: list[dict[str, str]] = []
        self.fullscreen_guard_reason = ""
        self._fullscreen_guard_log_ts = 0.0
        self.idle_triggered_at = ""
        self.display_mode_active = False
        self.requested_mode = "auto"
        self.control_source_runtime = "runtime"
        self.last_control_ts_runtime = self.runtime_start_ts
        self.last_control_reason_runtime = "idle_waiting"
        self.last_control_apply_ts = ""
        self.last_display_attach_ts = ""
        self.last_display_detach_ts = ""
        self.display_inhibitor_active = False
        self.inhibitor_backend = "none"
        self._display_inhibitor_proc: subprocess.Popen[str] | None = None
        self._last_idle_probe_ts = 0.0
        self._last_idle_probe_idle_s: float | None = None
        self._last_idle_probe_ok = False
        self._last_idle_probe_error_log_ts = 0.0
        self.session_idle_supported = False
        self.session_idle_seconds = 0.0
        self.idle_supported = False
        self.idle_last_error = ""
        self.idle_source = self.idle_trigger_source
        self._manual_enter_display_mode = bool(enter_display_mode)
        self._last_idle_wait_log_ts = 0.0

        acquired = self.gpu_lease.acquire(
            owner=self.lease_owner,
            mode=self.lease_mode,
            ttl_s=self.lease_ttl_s,
            policy=self.lease_mode,
        )
        if not acquired and self.lease_mode == "exclusive":
            message = (
                "exclusive GPU lease unavailable; another owner holds the lease. "
                f"lease_file={GPU_LEASE_PATH} detail={self.gpu_lease.last_error}"
            )
            self.log.log("lease_acquire_failed", mode=self.lease_mode, owner=self.lease_owner, error=self.gpu_lease.last_error)
            raise RuntimeError(message)
        self._lease_acquired = bool(acquired)
        self._lease_last_renew_ts = time.monotonic()
        self.log.log(
            "lease_acquired",
            acquired=self._lease_acquired,
            mode=self.lease_mode,
            owner=self.lease_owner,
            ttl_s=self.lease_ttl_s,
            lease_file=str(GPU_LEASE_PATH),
        )

        startup_ok = False
        self.renderer = None
        try:
            self._quiesce_inference_mode()
            renderer_gpu_backend_enabled = str(os.environ.get("DALI_FISHTANK_RENDERER_GPU_BACKEND", "1") or "1").strip() != "0"
            renderer_headless = bool(
                headless
                or self.frontend in {"ue5", "mirror"}
                or (self.frontend == "python" and self.idle_mode_enabled and not self.display_mode_active)
            )
            renderer_allow_gpu_backend = self.frontend not in {"ue5", "mirror"} and renderer_gpu_backend_enabled
            renderer_require_gpu = bool(require_gpu and renderer_allow_gpu_backend)
            self.renderer = FishTankRenderer(
                agent_count=agent_count,
                headless=renderer_headless,
                require_gpu=renderer_require_gpu,
                allow_gpu_backend=renderer_allow_gpu_backend,
                allow_visible_attach=(
                    self.frontend != "python"
                    or not self.idle_mode_enabled
                    or self.python_visible_attach_enabled
                ),
                control_bus=self.control_bus,
            )
            self.renderer.set_runtime_context(
                lease_mode=self.lease_mode,
                inference_quiesced=self.inference_quiesced,
                idle_mode_enabled=self.idle_mode_enabled,
                idle_trigger_source=self.idle_trigger_source,
                idle_triggered_at=self.idle_triggered_at,
                display_mode_active=self.display_mode_active,
                idle_inhibit_enabled=self.idle_inhibit_enabled,
                display_inhibitor_active=self.display_inhibitor_active,
                inhibitor_backend=self.inhibitor_backend,
            )
            startup_ok = True
        finally:
            if not startup_ok:
                self._unquiesce_inference_mode()
                if self._lease_acquired:
                    self.gpu_lease.release(owner=self.lease_owner)
        if self.abort_if_fullscreen_active and not renderer_headless and not self.idle_mode_enabled:
            blocked = self._refresh_fullscreen_guard()
            if blocked:
                message = "fullscreen application active; refusing non-idle display attach"
                self.log.log(
                    "fullscreen_guard_blocked_startup",
                    probe=self.fullscreen_guard_probe,
                    windows=self.fullscreen_guard_windows,
                    reason=message,
                )
                raise RuntimeError(message)
        if self._manual_enter_display_mode:
            self._enter_display_mode(reason="manual_flag")
        elif self.display_mode_active:
            self._enter_display_mode(reason="idle_disabled")
        elif self.idle_mode_enabled:
            self.log.log(
                "IDLE_WAITING",
                trigger_source=self.idle_trigger_source,
                idle_seconds=self.idle_seconds,
            )
        self.aesthetic = AestheticFeedbackStore()
        self.telegram_requested = bool(telegram_requested)
        self.telegram_debug_drain = bool(telegram_debug_drain)
        self.telegram_missing_keys = list(telegram_missing_keys or [])
        self.telegram_env_file = str(telegram_env_file or "")
        self._last_control_curiosity_ts = 0.0
        self._gateway_health_urls = self._resolve_gateway_health_urls()
        self._gateway_check_ts = 0.0
        self._gateway_ok = True
        self._gateway_reason = "unknown"
        self._shed_bad_streak = 0
        self._shed_good_streak = 0
        self._last_shed_reason = ""
        self.activity_signal = 0.0
        self.agent_activity_level = 0.0
        self.agent_count_active = 0
        self.coordination_density = 0.0
        self.routing_activity = 0.0
        self.interaction_activity = 0.0
        self.memory_activity = 0.0
        self.heavy_inference_suppressed = False
        self.semantic_activity_source_summary = ""
        self._activity_interaction_pulse_until = 0.0
        self._activity_curiosity_pulse_until = 0.0

        allowlist = [item.strip() for item in (telegram_allowlist or []) if item.strip()]
        self.telegram = None
        if telegram_enabled and telegram_token.strip() and allowlist:
            self.telegram = TelegramCommandInterface(
                token=telegram_token,
                allowed_chat_ids=set(allowlist),
                autoclear_webhook=telegram_autoclear_webhook,
                debug_drain_once=telegram_debug_drain,
            )
            self._wire_telegram_handlers(self.telegram)
        elif telegram_enabled:
            self.log.log(
                "telegram_disabled_missing_env",
                token_present=bool(telegram_token.strip()),
                chat_id_present=bool(allowlist),
            )
        if self.telegram_requested and self.telegram is None:
            self._emit_local_ping_fallback()

        self._threads: list[threading.Thread] = []
        self._warn_if_headless_without_consumer()

    def _warn_if_headless_without_consumer(self) -> None:
        if not self.renderer.headless:
            self.log.log("renderer_display_mode", mode="windowed", active_renderer_id=self.renderer.active_renderer_id)
            return
        if self.frontend == "ue5":
            self.log.log("renderer_display_mode", mode="headless", headless_consumer="ue5", frontend_launcher=self.frontend_process_path)
            return
        if self.frontend == "phase1":
            self.log.log("renderer_display_mode", mode="headless", headless_consumer="phase1", frontend_launcher=self.frontend_process_path)
            return
        if self.frontend == "mirror":
            self.log.log("renderer_display_mode", mode="headless", headless_consumer="work_mode_consciousness_mirror")
            return
        consumer = str(os.environ.get("DALI_FISHTANK_HEADLESS_CONSUMER", "") or "").strip()
        if consumer:
            self.log.log("renderer_display_mode", mode="headless", headless_consumer=consumer)
            return
        self.log.log(
            "headless_no_display_warning",
            message="HEADLESS=1 with no downstream consumer; nothing will appear on screen",
        )

    def _sync_frontend_state(self) -> None:
        proc = self.frontend_process
        if proc is None:
            self.frontend_process_running = False
            self.frontend_process_pid = 0
            self._sync_frontend_status_from_file()
            return

        returncode = proc.poll()
        if returncode is None:
            self.frontend_process_running = True
            self.frontend_process_pid = int(proc.pid or 0)
            self._sync_frontend_status_from_file()
            if (
                self.frontend_failure_streak > 0
                and self.frontend_last_start_monotonic > 0.0
                and (time.monotonic() - self.frontend_last_start_monotonic) >= self.frontend_success_reset_s
            ):
                self.frontend_failure_streak = 0
                self.frontend_restart_backoff_s = 0.0
                self.frontend_next_restart_monotonic = 0.0
                self.log.log(
                    "frontend_process_stable",
                    frontend=self.frontend,
                    path=self.frontend_process_path,
                    pid=self.frontend_process_pid,
                    runtime_s=round(time.monotonic() - self.frontend_last_start_monotonic, 3),
                )
            return

        now = time.monotonic()
        runtime_s = max(0.0, now - self.frontend_last_start_monotonic) if self.frontend_last_start_monotonic > 0.0 else 0.0
        self.frontend_last_runtime_s = runtime_s
        self.frontend_last_exit_code = int(returncode)
        self.frontend_last_exit_ts = utc_now_iso()
        self.frontend_process_running = False
        self.frontend_process_pid = 0
        self.frontend_process = None
        self.frontend_activation_pending = False
        clean_exit = returncode in {0, 143, -int(signal.SIGTERM)}
        if self.frontend_run_mode == "oneshot":
            self.frontend_failure_streak = 0 if clean_exit else (self.frontend_failure_streak + 1)
            self.frontend_restart_backoff_s = 0.0
            self.frontend_next_restart_monotonic = 0.0
        elif clean_exit or runtime_s >= self.frontend_success_reset_s:
            self.frontend_failure_streak = 0
            self.frontend_restart_backoff_s = 0.0
            self.frontend_next_restart_monotonic = 0.0
        else:
            self.frontend_failure_streak += 1
            self.frontend_restart_backoff_s = min(
                self.frontend_restart_cap_s,
                float(2 ** min(self.frontend_failure_streak - 1, 6)),
            )
            self.frontend_next_restart_monotonic = now + self.frontend_restart_backoff_s
        self.log.log(
            "frontend_process_exit",
            frontend=self.frontend,
            path=self.frontend_process_path,
            exit_code=returncode,
            runtime_s=round(runtime_s, 3),
            failure_streak=self.frontend_failure_streak,
            restart_backoff_s=round(self.frontend_restart_backoff_s, 3),
        )
        self._sync_frontend_status_from_file()
        if self._frontend_log_handle is not None:
            try:
                self._frontend_log_handle.close()
            except Exception:
                pass
            self._frontend_log_handle = None

    def _sync_frontend_status_from_file(self) -> None:
        if self.frontend != "phase1" or not self.frontend_status_path:
            return
        payload = load_json(Path(self.frontend_status_path), {})
        if not isinstance(payload, dict) or not payload:
            return
        self.frontend_last_status_payload = payload
        self.frontend_last_status = str(payload.get("status") or self.frontend_last_status or "idle")
        self.frontend_last_error = str(payload.get("error") or "")
        self.frontend_last_manifest_path = str(payload.get("manifest_path") or "")
        self.frontend_last_output_root = str(payload.get("output_root") or payload.get("run_root") or "")
        self.frontend_last_completed_ts = str(payload.get("completed_at") or payload.get("started_at") or self.frontend_last_completed_ts or "")

    def _write_phase1_status_snapshot(self, *, status: str, exit_code: int, error: str) -> None:
        if self.frontend != "phase1" or not self.frontend_status_path:
            return
        payload = dict(self.frontend_last_status_payload)
        payload.setdefault("schema_version", "dali.phase1.idle-status.v1")
        payload.setdefault("launcher_path", str(getattr(self, "frontend_process_path", "") or ""))
        payload.setdefault("output_root", str(getattr(self, "frontend_last_output_root", "") or ""))
        payload.setdefault("manifest_path", str(getattr(self, "frontend_last_manifest_path", "") or ""))
        payload["status"] = str(status)
        payload["exit_code"] = int(exit_code)
        payload["error"] = str(error)
        payload["completed_at"] = utc_now_iso()
        atomic_write_json(Path(self.frontend_status_path), payload)
        self.frontend_last_status_payload = payload
        self.frontend_last_status = str(status)
        self.frontend_last_error = str(error)
        self.frontend_last_completed_ts = str(payload["completed_at"])

    def _frontend_launch_env(self) -> dict[str, str]:
        env = os.environ.copy()
        uid = os.getuid()
        xdg_runtime_dir = str(env.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}").strip() or f"/run/user/{uid}"
        display = str(env.get("DISPLAY") or ":0").strip() or ":0"
        session_type = str(env.get("XDG_SESSION_TYPE") or "x11").strip() or "x11"
        dbus_address = str(env.get("DBUS_SESSION_BUS_ADDRESS") or f"unix:path={xdg_runtime_dir}/bus").strip()
        xauthority = str(env.get("XAUTHORITY") or (str(Path.home() / ".Xauthority"))).strip()
        lang = str(env.get("LANG") or "C.UTF-8").strip() or "C.UTF-8"

        env["DISPLAY"] = display
        env["XDG_RUNTIME_DIR"] = xdg_runtime_dir
        env["XDG_SESSION_TYPE"] = session_type
        env["DBUS_SESSION_BUS_ADDRESS"] = dbus_address
        env["LANG"] = lang
        if xauthority:
            env["XAUTHORITY"] = xauthority

        self.frontend_launch_env_summary = {
            "DISPLAY": display,
            "XDG_RUNTIME_DIR": xdg_runtime_dir,
            "XDG_SESSION_TYPE": session_type,
            "DBUS_SESSION_BUS_ADDRESS": dbus_address,
            "XAUTHORITY": xauthority,
            "LANG": lang,
        }
        return env

    def _start_frontend(self) -> None:
        if self.frontend not in {"ue5", "phase1"}:
            return

        self._sync_frontend_state()
        if self.frontend_process_running:
            return
        if self.frontend_run_mode == "oneshot" and not self.frontend_activation_pending:
            return

        now = time.monotonic()
        if self.frontend_run_mode == "persistent" and self.frontend_next_restart_monotonic > now:
            if (now - self._frontend_restart_wait_log_ts) >= 5.0:
                self.log.log(
                    "frontend_restart_wait",
                    frontend=self.frontend,
                    path=self.frontend_process_path,
                    ready_in_s=round(self.frontend_next_restart_monotonic - now, 3),
                    failure_streak=self.frontend_failure_streak,
                    last_exit_code=self.frontend_last_exit_code,
                )
                self._frontend_restart_wait_log_ts = now
            return

        launcher_path = Path(self.frontend_process_path)
        if not launcher_path.exists():
            if self.frontend_run_mode == "oneshot":
                self.frontend_activation_pending = False
                self.frontend_last_status = "missing_launcher"
                self.frontend_last_error = f"missing launcher: {launcher_path}"
            self.log.log("frontend_process_missing", frontend=self.frontend, path=str(launcher_path))
            return
        if not os.access(launcher_path, os.X_OK):
            if self.frontend_run_mode == "oneshot":
                self.frontend_activation_pending = False
                self.frontend_last_status = "launcher_not_executable"
                self.frontend_last_error = f"launcher not executable: {launcher_path}"
            self.log.log("frontend_process_not_executable", frontend=self.frontend, path=str(launcher_path))
            return

        self.frontend_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._frontend_log_handle = self.frontend_log_path.open("a", encoding="utf-8")
        env = self._frontend_launch_env()
        env.setdefault("PYTHONUNBUFFERED", "1")
        if self.frontend == "phase1" and self.frontend_status_path:
            env["DALI_FISHTANK_PHASE1_STATUS_PATH"] = self.frontend_status_path
        try:
            self.frontend_last_start_monotonic = time.monotonic()
            self.frontend_last_start_ts = utc_now_iso()
            self.frontend_last_status = "launching"
            self.frontend_last_error = ""
            self.frontend_process = subprocess.Popen(
                [str(launcher_path)],
                cwd=str(launcher_path.parent),
                stdout=self._frontend_log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
        except Exception as exc:
            self.frontend_process = None
            self.frontend_process_running = False
            self.frontend_process_pid = 0
            self.frontend_last_start_monotonic = 0.0
            self.frontend_last_start_ts = ""
            self.frontend_activation_pending = False
            self.frontend_last_status = "start_failed"
            self.frontend_last_error = str(exc)
            self.log.log("frontend_process_start_failed", frontend=self.frontend, path=str(launcher_path), error=str(exc))
            if self._frontend_log_handle is not None:
                try:
                    self._frontend_log_handle.close()
                except Exception:
                    pass
                self._frontend_log_handle = None
            return

        time.sleep(0.05)
        self._sync_frontend_state()
        self.log.log(
            "frontend_process_started",
            frontend=self.frontend,
            path=str(launcher_path),
            pid=self.frontend_process_pid,
            fullscreen_requested=self.frontend_fullscreen_requested,
            display=self.frontend_launch_env_summary.get("DISPLAY", ""),
            session_type=self.frontend_launch_env_summary.get("XDG_SESSION_TYPE", ""),
        )

    def _stop_frontend(self) -> None:
        proc = self.frontend_process
        self.frontend_process = None
        self.frontend_activation_pending = False
        stop_exit_code = self.frontend_last_exit_code if self.frontend_last_exit_code is not None else 0
        terminated_running_proc = False
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    stop_exit_code = int(proc.wait(timeout=5.0))
                    terminated_running_proc = True
                else:
                    stop_exit_code = int(proc.returncode or 0)
            except Exception:
                try:
                    proc.kill()
                    terminated_running_proc = True
                except Exception:
                    pass
        self.frontend_process_running = False
        self.frontend_process_pid = 0
        if terminated_running_proc and self.frontend == "phase1":
            self.frontend_last_exit_code = stop_exit_code
            self._write_phase1_status_snapshot(
                status="terminated",
                exit_code=stop_exit_code,
                error="terminated by runtime control path",
            )
        if self._frontend_log_handle is not None:
            try:
                self._frontend_log_handle.close()
            except Exception:
                pass
            self._frontend_log_handle = None
        if self.frontend in {"ue5", "phase1"}:
            self.log.log("frontend_process_stopped", frontend=self.frontend, path=self.frontend_process_path)

    def _runtime_state_fields(self) -> dict[str, Any]:
        try:
            self._sync_frontend_state()
        except Exception:
            pass
        display_mode_active = bool(getattr(self, "display_mode_active", False))
        requested_mode = str(getattr(self, "requested_mode", "auto") or "auto")
        effective_mode = str(getattr(self, "effective_mode", "") or "")
        if not effective_mode:
            effective_mode = "on" if display_mode_active else ("off" if requested_mode == "off" else "auto")
        control_source = str(getattr(self, "control_source_runtime", getattr(self, "control_source", "")) or "")
        last_control_ts = str(
            getattr(self, "last_control_ts_runtime", getattr(self, "last_control_ts", getattr(self, "runtime_start_ts", "")))
            or getattr(self, "runtime_start_ts", "")
        )
        last_control_reason = str(getattr(self, "last_control_reason_runtime", getattr(self, "last_control_reason", "")) or "")
        effective_activation_source = str(
            getattr(
                self,
                "effective_activation_source",
                (
                    "frontend_ue5"
                    if display_mode_active and getattr(self, "frontend", "python") == "ue5" and getattr(self, "frontend_process_running", False)
                    else (
                        "mirror_headless"
                        if display_mode_active and getattr(self, "frontend", "python") == "mirror"
                        else (
                        "frontend_phase1"
                        if getattr(self, "frontend", "python") == "phase1"
                        and (
                            getattr(self, "frontend_process_running", False)
                            or str(getattr(self, "frontend_last_status", "") or "") in {"succeeded", "failed", "start_failed"}
                        )
                        else ("renderer_python" if display_mode_active else "none")
                        )
                    )
                ),
            )
            or "none"
        )
        return {
            "requested_mode": requested_mode,
            "effective_mode": effective_mode,
            "control_source": control_source,
            "last_control_ts": last_control_ts,
            "last_control_reason": last_control_reason,
            "effective_activation_source": effective_activation_source,
            "runtime_instance_id": str(getattr(self, "runtime_instance_id", "")),
            "pid": int(getattr(self, "pid", 0) or 0),
            "start_ts": str(getattr(self, "runtime_start_ts", "") or ""),
            "frontend": str(getattr(self, "frontend", "python") or "python"),
            "frontend_process_running": bool(getattr(self, "frontend_process_running", False)),
            "frontend_process_pid": int(getattr(self, "frontend_process_pid", 0) or 0),
            "frontend_process_path": str(getattr(self, "frontend_process_path", "") or ""),
            "frontend_last_start_ts": str(getattr(self, "frontend_last_start_ts", "") or ""),
            "frontend_last_exit_code": getattr(self, "frontend_last_exit_code", None),
            "frontend_last_exit_ts": str(getattr(self, "frontend_last_exit_ts", "") or ""),
            "frontend_last_runtime_s": round(float(getattr(self, "frontend_last_runtime_s", 0.0) or 0.0), 3),
            "frontend_failure_streak": int(getattr(self, "frontend_failure_streak", 0) or 0),
            "frontend_restart_backoff_s": round(float(getattr(self, "frontend_restart_backoff_s", 0.0) or 0.0), 3),
            "frontend_restart_ready_in_s": round(
                max(0.0, float(getattr(self, "frontend_next_restart_monotonic", 0.0) or 0.0) - time.monotonic()),
                3,
            )
            if float(getattr(self, "frontend_next_restart_monotonic", 0.0) or 0.0) > 0.0
            else 0.0,
            "frontend_display": getattr(self, "frontend_launch_env_summary", {}).get("DISPLAY", str(os.environ.get("DISPLAY", "") or "")),
            "frontend_session_type": getattr(self, "frontend_launch_env_summary", {}).get(
                "XDG_SESSION_TYPE",
                str(os.environ.get("XDG_SESSION_TYPE", "") or ""),
            ),
            "frontend_run_mode": str(getattr(self, "frontend_run_mode", "none") or "none"),
            "frontend_last_status": str(getattr(self, "frontend_last_status", "idle") or "idle"),
            "frontend_last_error": str(getattr(self, "frontend_last_error", "") or ""),
            "frontend_last_manifest_path": str(getattr(self, "frontend_last_manifest_path", "") or ""),
            "frontend_last_output_root": str(getattr(self, "frontend_last_output_root", "") or ""),
            "frontend_last_completed_ts": str(getattr(self, "frontend_last_completed_ts", "") or ""),
            "frontend_status_path": str(getattr(self, "frontend_status_path", "") or ""),
            "last_idle_activation_ts": str(getattr(self, "last_idle_activation_ts", "") or ""),
            "last_control_apply_ts": str(getattr(self, "last_control_apply_ts", "") or ""),
            "last_display_attach_ts": str(getattr(self, "last_display_attach_ts", "") or ""),
            "last_display_detach_ts": str(getattr(self, "last_display_detach_ts", "") or ""),
            "schedule_enabled": bool(getattr(self, "schedule_enabled", False)),
            "schedule_allowed": bool(getattr(self, "schedule_allowed", False)),
            "schedule_latch_display": bool(getattr(self, "schedule_latch_display", False)),
            "schedule_window_start": str(getattr(self, "schedule_window_start", "") or ""),
            "schedule_window_end": str(getattr(self, "schedule_window_end", "") or ""),
            "schedule_timezone": str(getattr(self, "schedule_timezone", "") or ""),
            "idle_enabled": bool(getattr(self, "idle_enabled", getattr(self, "idle_mode_enabled", False))),
            "idle_mode_enabled": bool(getattr(self, "idle_mode_enabled", False)),
            "idle_seconds": float(getattr(self, "idle_seconds", 0.0) or 0.0),
            "idle_supported": bool(getattr(self, "idle_supported", getattr(self, "session_idle_supported", False))),
            "idle_threshold_seconds": float(getattr(self, "idle_threshold_seconds", getattr(self, "idle_seconds", 0.0)) or 0.0),
            "idle_last_check_ok": bool(getattr(self, "idle_last_check_ok", getattr(self, "_last_idle_probe_ok", False))),
            "idle_last_error": str(getattr(self, "idle_last_error", "") or ""),
            "idle_source": str(getattr(self, "idle_source", getattr(self, "idle_trigger_source", "")) or ""),
            "session_idle_supported": bool(getattr(self, "session_idle_supported", False)),
            "session_idle_seconds": float(getattr(self, "session_idle_seconds", getattr(self, "_last_idle_probe_idle_s", 0.0)) or 0.0),
            "idle_last_input_ts": str(getattr(self, "idle_last_input_ts", "") or ""),
            "idle_reason": str(getattr(self, "idle_reason", "") or ""),
            "idle_triggered": bool(getattr(self, "idle_triggered", display_mode_active)),
            "idle_trigger_source": str(getattr(self, "idle_trigger_source", "") or ""),
            "idle_triggered_at": str(getattr(self, "idle_triggered_at", "") or ""),
            "fullscreen_guard_enabled": bool(getattr(self, "abort_if_fullscreen_active", False)),
            "fullscreen_guard_probe": str(getattr(self, "fullscreen_guard_probe", "disabled") or "disabled"),
            "fullscreen_guard_blocked": bool(getattr(self, "fullscreen_guard_blocked", False)),
            "fullscreen_guard_reason": str(getattr(self, "fullscreen_guard_reason", "") or ""),
            "fullscreen_guard_windows": list(getattr(self, "fullscreen_guard_windows", []) or []),
            "manual_override_mode": str(getattr(self, "manual_override_mode", "none") or "none"),
            "display_mode_active": display_mode_active,
            "display_mode_reason": str(getattr(self, "display_mode_reason", last_control_reason) or ""),
            "inhibit_active": bool(getattr(self, "inhibit_active", getattr(self, "display_inhibitor_active", False))),
            "inhibit_reason": str(getattr(self, "inhibit_reason", "Dali Cathedral display mode" if display_mode_active else "") or ""),
            "idle_inhibit_enabled": bool(getattr(self, "idle_inhibit_enabled", False)),
            "display_inhibitor_active": bool(getattr(self, "display_inhibitor_active", False)),
            "inhibitor_backend": str(getattr(self, "inhibitor_backend", "none") or "none"),
            "display_blank_inhibit_active": bool(getattr(self, "display_blank_inhibit_active", getattr(self, "display_inhibitor_active", False))),
            "screensaver_inhibit_active": bool(getattr(self, "screensaver_inhibit_active", getattr(self, "display_inhibitor_active", False))),
            "session_inhibit_active": bool(getattr(self, "session_inhibit_active", False)),
            "dpms_override_active": bool(getattr(self, "dpms_override_active", False)),
            "lease_owner": str(getattr(self, "lease_owner", "") or ""),
            "base_rate_hz": float(getattr(self, "rate_hz", 0.0) or 0.0),
            "display_rate_cap_hz": float(getattr(self, "display_rate_hz", 0.0) or 0.0),
            "display_rate_mode": str(getattr(self, "display_rate_mode", "") or ""),
            "loop_rate_target_hz": float(getattr(self, "loop_rate_target_hz", 0.0) or 0.0),
            "loop_rate_source": str(getattr(self, "loop_rate_source", "") or ""),
            "loop_sleep_ms": float(getattr(self, "loop_sleep_ms", 0.0) or 0.0),
            "rate_limited": bool(getattr(self, "rate_limited", False)),
            "activity_signal": round(float(getattr(self, "activity_signal", 0.0) or 0.0), 6),
            "agent_activity_level": round(float(getattr(self, "agent_activity_level", 0.0) or 0.0), 6),
            "agent_count_active": int(getattr(self, "agent_count_active", 0) or 0),
            "coordination_density": round(float(getattr(self, "coordination_density", 0.0) or 0.0), 6),
            "routing_activity": round(float(getattr(self, "routing_activity", 0.0) or 0.0), 6),
            "interaction_activity": round(float(getattr(self, "interaction_activity", 0.0) or 0.0), 6),
            "memory_activity": round(float(getattr(self, "memory_activity", 0.0) or 0.0), 6),
            "heavy_inference_suppressed": bool(getattr(self, "heavy_inference_suppressed", False)),
            "semantic_activity_source_summary": str(getattr(self, "semantic_activity_source_summary", "") or ""),
        }

    def _state_payload(self, state: dict[str, Any]) -> dict[str, Any]:
        payload = dict(state)
        payload.update(self._runtime_state_fields())
        payload["fullscreen_requested"] = bool(self.frontend_fullscreen_requested)

        if self.frontend == "ue5" and self.frontend_process_running and self.display_mode_active:
            payload["active_renderer_id"] = "ue5_dali_mirror"
            payload["active_renderer_name"] = "UE5 DaliMirror"
            payload["frontend"] = "ue5"
            payload["window_visible"] = True
            payload["display_attached"] = True
            payload["fullscreen_attached"] = bool(self.frontend_fullscreen_requested)
            payload["monitor_bound"] = True
            return payload
        if self.frontend == "mirror":
            payload["window_visible"] = False
            payload["display_attached"] = False
            payload["fullscreen_attached"] = False
            payload["monitor_bound"] = False
            return payload

        payload["window_visible"] = (
            bool(payload["window_visible"])
            if "window_visible" in payload
            else bool(not self.renderer.headless and self.display_mode_active)
        )
        payload["display_attached"] = (
            bool(payload["display_attached"])
            if "display_attached" in payload
            else bool(payload["window_visible"])
        )
        renderer_backend = str(payload.get("backend", getattr(self.renderer, "backend", "")) or "")
        renderer_tk_fullscreen = (
            renderer_backend == "tk-work-window" and bool(payload["window_visible"]) and bool(self.frontend_fullscreen_requested)
        )
        renderer_fullscreen = renderer_backend.endswith("fullscreen") or renderer_tk_fullscreen
        payload["fullscreen_attached"] = (
            bool(payload["fullscreen_attached"])
            if "fullscreen_attached" in payload
            else bool(renderer_fullscreen and payload["window_visible"])
        )
        if renderer_tk_fullscreen:
            payload["fullscreen_attached"] = True
        payload["monitor_bound"] = (
            bool(payload["monitor_bound"])
            if "monitor_bound" in payload
            else bool(payload["fullscreen_attached"])
        )
        if renderer_tk_fullscreen:
            payload["monitor_bound"] = True
        return payload

    def _emit_local_ping_fallback(self) -> None:
        missing = ",".join(self.telegram_missing_keys) if self.telegram_missing_keys else "unknown"
        self.log.log(
            "local_ping",
            message="telegram unavailable; renderer running",
            env_file=self.telegram_env_file,
            missing_keys=missing,
            active_renderer_id=self.renderer.active_renderer_id,
            gpu_required=self.renderer.require_gpu,
            display_mode=("headless" if self.renderer.headless else "windowed"),
        )
        print(
            f"LOCAL_PING telegram_unavailable env_file={self.telegram_env_file} missing_keys={missing}",
            flush=True,
        )

    def _hash_payload(self, payload: dict[str, Any]) -> str:
        blob = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def _record_telegram_control_event(
        self,
        *,
        command: str,
        controls: dict[str, float],
        bucket: str = "novelty",
        note: str = "",
    ) -> None:
        state = self._read_json(FISHTANK_STATE_PATH)
        fishtank_hash = self._hash_payload(state) if state else "missing"
        record = {
            "ts": utc_now_iso(),
            "command": str(command),
            "controls": {str(k): float(v) for k, v in controls.items()},
            "fishtank_state_hash": fishtank_hash,
            "note": str(note),
        }
        target = NOVELTY_ARCHIVE_DIR / "telegram_controls.jsonl"
        if bucket == "aesthetic":
            target = AESTHETIC_EVENTS_DIR / "telegram_controls.jsonl"
        append_jsonl(target, record)

    def _parse_value_ttl(self, arg: str, *, default_value: float, default_seconds: float) -> tuple[float, float]:
        parts = [item for item in str(arg or "").split() if item]
        value = float(default_value)
        ttl_seconds = float(default_seconds)
        if len(parts) >= 1:
            try:
                value = float(parts[0])
            except Exception:
                value = float(default_value)
        if len(parts) >= 2:
            try:
                ttl_seconds = float(parts[1])
            except Exception:
                ttl_seconds = float(default_seconds)
        ttl_seconds = max(2.0, min(300.0, ttl_seconds))
        return value, ttl_seconds

    def _post_json(self, url: str, payload: dict[str, Any], *, timeout: float = 1.5) -> tuple[bool, str]:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = int(getattr(resp, "status", 0) or 0)
                raw = resp.read().decode("utf-8", errors="replace")[:220]
            return (200 <= code < 300), f"http_{code}:{raw}"
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")[:220]
            return False, f"http_{int(exc.code)}:{body_text}"
        except Exception as exc:
            return False, f"{exc.__class__.__name__}:{exc}"

    def _quiesce_inference_mode(self) -> None:
        if not self.quiesce_enabled:
            self.inference_quiesced = False
            self.log.log("quiesce_configured", enabled=False)
            return
        configured = bool(self.quiesce_endpoint) or bool(self.quiesce_units)
        if not configured:
            self.inference_quiesced = False
            self.log.log("quiesce_configured", enabled=True, configured=0, message="no endpoint and no units")
            return

        endpoint_ok = True
        if self.quiesce_endpoint:
            ok, detail = self._post_json(
                self.quiesce_endpoint,
                {"mode": "display", "ttl_s": float(self.lease_ttl_s)},
            )
            endpoint_ok = ok
            self.log.log("quiesce_endpoint", url=self.quiesce_endpoint, ok=ok, detail=detail)

        requested_units_total = len(self.quiesce_units)
        stopped_units: list[str] = []
        requested_units = 0
        for unit in self.quiesce_units:
            if unit == "openclaw-gateway.service":
                self.log.log("quiesce_skip_unit", unit=unit, reason="gateway_protected")
                continue
            if unit not in self._quiesce_allowlist:
                self.log.log("quiesce_skip_unit", unit=unit, reason="not_allowlisted")
                continue
            requested_units += 1
            try:
                import subprocess

                proc = subprocess.run(
                    ["systemctl", "--user", "stop", unit],
                    capture_output=True,
                    text=True,
                    timeout=4.0,
                    check=False,
                )
            except Exception as exc:
                self.log.log("quiesce_stop_error", unit=unit, error=str(exc))
                continue
            if proc.returncode == 0:
                stopped_units.append(unit)
                self.log.log("quiesce_unit_stopped", unit=unit)
            else:
                self.log.log("quiesce_stop_failed", unit=unit, rc=proc.returncode, stderr=(proc.stderr or "").strip()[:180])
        self._quiesced_units = stopped_units
        endpoint_applied = (not self.quiesce_endpoint) or endpoint_ok
        units_applied = (requested_units_total == 0) or bool(stopped_units)
        self.inference_quiesced = bool(endpoint_applied and units_applied)
        self.log.log(
            "quiesce_applied",
            enabled=True,
            endpoint=bool(self.quiesce_endpoint),
            endpoint_ok=endpoint_ok,
            units_requested=len(self.quiesce_units),
            units_allowlisted=requested_units,
            units_stopped=stopped_units,
            inference_quiesced=self.inference_quiesced,
        )

    def _unquiesce_inference_mode(self) -> None:
        if self.quiesce_endpoint:
            ok, detail = self._post_json(self.quiesce_endpoint, {"mode": "inference"})
            self.log.log("unquiesce_endpoint", url=self.quiesce_endpoint, ok=ok, detail=detail)
        if self._quiesced_units:
            for unit in list(self._quiesced_units):
                try:
                    import subprocess

                    proc = subprocess.run(
                        ["systemctl", "--user", "start", unit],
                        capture_output=True,
                        text=True,
                        timeout=4.0,
                        check=False,
                    )
                except Exception as exc:
                    self.log.log("unquiesce_start_error", unit=unit, error=str(exc))
                    continue
                if proc.returncode == 0:
                    self.log.log("unquiesce_unit_started", unit=unit)
                else:
                    self.log.log(
                        "unquiesce_start_failed",
                        unit=unit,
                        rc=proc.returncode,
                        stderr=(proc.stderr or "").strip()[:180],
                    )
        self._quiesced_units = []
        self.inference_quiesced = False

    def _set_idle_probe_result(
        self,
        *,
        ok: bool,
        idle_s: float | None,
        source: str,
        session_supported: bool,
        error: str = "",
    ) -> tuple[bool, float | None]:
        self._last_idle_probe_ok = ok
        self._last_idle_probe_idle_s = idle_s
        self.session_idle_supported = session_supported
        self.session_idle_seconds = float(idle_s or 0.0) if session_supported and idle_s is not None else 0.0
        self.idle_supported = ok
        self.idle_source = source
        self.idle_last_error = error
        return ok, idle_s

    def _probe_gnome_idle_seconds(self) -> tuple[bool, float | None]:
        env = os.environ.copy()
        uid = os.getuid()
        env.setdefault("DISPLAY", str(env.get("DISPLAY") or ":0").strip() or ":0")
        env.setdefault("XDG_RUNTIME_DIR", str(env.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}").strip() or f"/run/user/{uid}")
        env.setdefault(
            "DBUS_SESSION_BUS_ADDRESS",
            str(env.get("DBUS_SESSION_BUS_ADDRESS") or f"unix:path={env['XDG_RUNTIME_DIR']}/bus").strip(),
        )
        xauthority = str(env.get("XAUTHORITY") or (str(Path.home() / ".Xauthority"))).strip()
        if xauthority:
            env["XAUTHORITY"] = xauthority
        try:
            proc = subprocess.run(
                [
                    "gdbus",
                    "call",
                    "--session",
                    "--dest",
                    "org.gnome.Mutter.IdleMonitor",
                    "--object-path",
                    "/org/gnome/Mutter/IdleMonitor/Core",
                    "--method",
                    "org.gnome.Mutter.IdleMonitor.GetIdletime",
                ],
                capture_output=True,
                text=True,
                timeout=0.4,
                check=False,
                env=env,
            )
        except Exception as exc:
            if (time.monotonic() - self._last_idle_probe_error_log_ts) >= 30.0:
                self._last_idle_probe_error_log_ts = time.monotonic()
                self.log.log("idle_probe_gnome_error", error=str(exc))
            return False, None
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            if stderr and (time.monotonic() - self._last_idle_probe_error_log_ts) >= 30.0:
                self._last_idle_probe_error_log_ts = time.monotonic()
                self.log.log("idle_probe_gnome_failed", rc=proc.returncode, stderr=stderr[:200])
            return False, None
        match = re.search(r"uint64\s+(\d+)", proc.stdout or "")
        if match is None:
            return False, None
        idle_ms = int(match.group(1))
        return True, max(0.0, float(idle_ms) / 1000.0)

    def _resolve_idle_session_id(self) -> str:
        session_id = str(os.environ.get("XDG_SESSION_ID", "") or "").strip()
        if session_id:
            return session_id

        cached_session_id = str(getattr(self, "_idle_session_id_hint", "") or "").strip()
        cached_refresh_ts = float(getattr(self, "_idle_session_id_hint_ts", 0.0) or 0.0)
        now = time.monotonic()
        if cached_session_id and (now - cached_refresh_ts) < 60.0:
            return cached_session_id

        try:
            proc = subprocess.run(
                ["loginctl", "list-sessions", "--no-legend"],
                capture_output=True,
                text=True,
                timeout=0.4,
                check=False,
            )
        except Exception:
            return ""
        if proc.returncode != 0:
            return ""

        uid_text = str(os.getuid())
        candidate_ids: list[str] = []
        for raw in (proc.stdout or "").splitlines():
            parts = raw.split()
            if len(parts) >= 2 and parts[1] == uid_text:
                candidate_ids.append(parts[0])
        if not candidate_ids:
            return ""

        def _rank_session(sid: str) -> tuple[int, int, int, int]:
            try:
                meta = subprocess.run(
                    [
                        "loginctl",
                        "show-session",
                        sid,
                        "-p",
                        "Remote",
                        "-p",
                        "Type",
                        "-p",
                        "Active",
                        "-p",
                        "State",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=0.4,
                    check=False,
                )
            except Exception:
                return (0, 0, 0, 0)
            if meta.returncode != 0:
                return (0, 0, 0, 0)
            values: dict[str, str] = {}
            for line in (meta.stdout or "").splitlines():
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().lower()
            remote_score = 1 if values.get("Remote") == "no" else 0
            type_score = 1 if values.get("Type") in {"x11", "wayland"} else 0
            active_score = 1 if values.get("Active") == "yes" else 0
            state_score = 1 if values.get("State") == "active" else 0
            return (remote_score, type_score, active_score, state_score)

        best_id = max(candidate_ids, key=_rank_session)
        setattr(self, "_idle_session_id_hint", best_id)
        setattr(self, "_idle_session_id_hint_ts", now)
        return best_id

    def _probe_session_idle_seconds(self) -> tuple[bool, float | None]:
        now = time.monotonic()
        if (now - self._last_idle_probe_ts) < 1.0:
            return self._last_idle_probe_ok, self._last_idle_probe_idle_s
        self._last_idle_probe_ts = now
        self._last_idle_probe_ok = False
        self._last_idle_probe_idle_s = None
        session_id = self._resolve_idle_session_id()
        cmd: list[str] = ["loginctl", "show-session", session_id, "-p", "IdleHint", "-p", "IdleSinceHintMonotonic"] if session_id else []
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=0.4,
                check=False,
            )
        except Exception as exc:
            if (now - self._last_idle_probe_error_log_ts) >= 30.0:
                self._last_idle_probe_error_log_ts = now
                self.log.log("idle_probe_error", error=str(exc))
            ok, idle_s = self._probe_gnome_idle_seconds()
            if ok:
                return self._set_idle_probe_result(ok=True, idle_s=idle_s, source="gnome", session_supported=False)
            return self._set_idle_probe_result(
                ok=False,
                idle_s=None,
                source=self.idle_trigger_source,
                session_supported=False,
                error=str(exc),
            )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            if stderr and (now - self._last_idle_probe_error_log_ts) >= 30.0:
                self._last_idle_probe_error_log_ts = now
                self.log.log("idle_probe_failed", rc=proc.returncode, stderr=stderr[:200])
            ok, idle_s = self._probe_gnome_idle_seconds()
            if ok:
                return self._set_idle_probe_result(ok=True, idle_s=idle_s, source="gnome", session_supported=False)
            return self._set_idle_probe_result(
                ok=False,
                idle_s=None,
                source=self.idle_trigger_source,
                session_supported=False,
                error=stderr[:200],
            )
        values: dict[str, str] = {}
        for raw in (proc.stdout or "").splitlines():
            if "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            values[key.strip()] = value.strip()
        idle_hint = values.get("IdleHint", "").lower()
        if idle_hint != "yes":
            return self._set_idle_probe_result(ok=True, idle_s=0.0, source="session", session_supported=True)
        idle_since_raw = values.get("IdleSinceHintMonotonic", "0")
        try:
            idle_since_usec = int(idle_since_raw or "0")
        except Exception:
            idle_since_usec = 0
        if idle_since_usec <= 0:
            ok, idle_s = self._probe_gnome_idle_seconds()
            if ok:
                return self._set_idle_probe_result(ok=True, idle_s=idle_s, source="gnome", session_supported=False)
            return self._set_idle_probe_result(
                ok=False,
                idle_s=None,
                source=self.idle_trigger_source,
                session_supported=False,
                error="idle_since_hint_missing",
            )
        now_usec = int(time.monotonic() * 1_000_000.0)
        idle_s = max(0.0, float(now_usec - idle_since_usec) / 1_000_000.0)
        return self._set_idle_probe_result(ok=True, idle_s=idle_s, source="session", session_supported=True)

    def _probe_idle_seconds(self) -> tuple[bool, float | None]:
        if self.idle_trigger_source == "gnome":
            ok, idle_s = self._probe_gnome_idle_seconds()
            if ok:
                return self._set_idle_probe_result(ok=True, idle_s=idle_s, source="gnome", session_supported=False)
            return self._set_idle_probe_result(
                ok=False,
                idle_s=None,
                source="gnome",
                session_supported=False,
                error="gnome_idle_unavailable",
            )
        return self._probe_session_idle_seconds()

    def _refresh_fullscreen_guard(self) -> bool:
        if not self.abort_if_fullscreen_active:
            self.fullscreen_guard_probe = "disabled"
            self.fullscreen_guard_blocked = False
            self.fullscreen_guard_windows = []
            self.fullscreen_guard_reason = ""
            return False
        windows, probe = _detect_other_fullscreen_windows()
        self.fullscreen_guard_probe = probe
        self.fullscreen_guard_windows = list(windows)
        self.fullscreen_guard_blocked = bool(windows)
        if windows:
            first = windows[0]
            self.fullscreen_guard_reason = (
                f"fullscreen app active: {first.get('title') or first.get('wm_class') or first.get('window_id')}"
            )
        else:
            self.fullscreen_guard_reason = ""
        return self.fullscreen_guard_blocked

    def _start_display_inhibitor(self) -> None:
        if self.display_inhibitor_active or not self.idle_inhibit_enabled:
            return
        try:
            self._display_inhibitor_proc = subprocess.Popen(
                [
                    "systemd-inhibit",
                    "--what=idle:sleep",
                    "--why=Dali Cathedral display active",
                    "sleep",
                    "infinity",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception as exc:
            self.display_inhibitor_active = False
            self.inhibitor_backend = "none"
            self.log.log("display_inhibitor_start_failed", error=str(exc))
            return
        time.sleep(0.05)
        if self._display_inhibitor_proc.poll() is None:
            self.display_inhibitor_active = True
            self.inhibitor_backend = "systemd-inhibit-child"
            self.log.log("display_inhibitor_started", backend=self.inhibitor_backend)
            return
        self.display_inhibitor_active = False
        self.inhibitor_backend = "none"
        self.log.log("display_inhibitor_start_failed", error="inhibitor_process_exited")

    def _stop_display_inhibitor(self) -> None:
        proc = self._display_inhibitor_proc
        self._display_inhibitor_proc = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.display_inhibitor_active = False
        self.inhibitor_backend = "none"

    def _enter_display_mode(self, *, reason: str) -> None:
        if self.display_mode_active:
            return
        if self.frontend == "python" and not self.python_visible_attach_enabled:
            now = time.monotonic()
            if (now - self._python_visible_attach_block_log_ts) >= 5.0:
                self.log.log(
                    "DISPLAY_MODE_BLOCKED",
                    reason=reason,
                    frontend=self.frontend,
                    blocker="python_visible_attach_disabled",
                )
                self._python_visible_attach_block_log_ts = now
            return
        self.display_mode_active = True
        self.display_mode_reason = reason
        self.idle_triggered_at = utc_now_iso()
        self.last_idle_activation_ts = self.idle_triggered_at
        self.last_display_attach_ts = self.idle_triggered_at
        self.last_control_apply_ts = self.idle_triggered_at
        self.last_control_ts_runtime = self.idle_triggered_at
        self.last_control_reason_runtime = reason
        if self.frontend == "phase1":
            self.frontend_activation_pending = True
            self.frontend_last_status = "queued"
            self.frontend_last_error = ""
            if reason.endswith("_idle") or reason == "idle_disabled":
                self._phase1_idle_episode_consumed = True
        self.log.log(
            "IDLE_TRIGGERED",
            trigger_source=self.idle_trigger_source,
            reason=reason,
            idle_seconds=self.idle_seconds,
        )
        if self.idle_inhibit_enabled:
            self._start_display_inhibitor()
        self.log.log(
            "DISPLAY_MODE_ENTER",
            reason=reason,
            display_inhibitor_active=self.display_inhibitor_active,
            inhibitor_backend=self.inhibitor_backend,
        )
        self._start_frontend()

    def _exit_display_mode(self, *, reason: str) -> None:
        if not self.display_mode_active:
            return
        self._stop_frontend()
        self._stop_display_inhibitor()
        self.display_mode_active = False
        self.display_mode_reason = reason
        self.last_display_detach_ts = utc_now_iso()
        self.last_control_apply_ts = self.last_display_detach_ts
        self.last_control_ts_runtime = self.last_display_detach_ts
        self.last_control_reason_runtime = reason
        self.log.log("DISPLAY_MODE_EXIT", reason=reason)

    def _apply_requested_mode_override(self) -> bool:
        control_state = load_fishtank_control_state()
        requested_mode = str(control_state.get("requested_mode") or "auto").strip().lower()
        if requested_mode not in {"on", "off", "auto"}:
            requested_mode = "auto"
        self.requested_mode = requested_mode
        self.control_source_runtime = str(control_state.get("control_source") or "runtime")
        self.last_control_ts_runtime = str(control_state.get("last_control_ts") or self.runtime_start_ts)
        self.last_control_reason_runtime = str(control_state.get("last_control_reason") or "idle_waiting")
        if requested_mode != "on":
            self._phase1_requested_mode_on_consumed_ts = ""

        if requested_mode == "on":
            if self.frontend == "phase1" and self._phase1_requested_mode_on_consumed_ts == self.last_control_ts_runtime:
                return True
            if not self.display_mode_active:
                self._enter_display_mode(reason=self.last_control_reason_runtime or "control_on")
            return True
        if requested_mode == "off":
            if self.display_mode_active:
                self._exit_display_mode(reason=self.last_control_reason_runtime or "control_off")
            return True
        if (
            requested_mode == "auto"
            and self.display_mode_active
            and str(self.last_control_reason_runtime or "").startswith("dismiss_")
        ):
            self._exit_display_mode(reason=self.last_control_reason_runtime or "dismiss")
            write_fishtank_control_state(
                "auto",
                source="runtime",
                reason="idle_waiting",
            )
            self.requested_mode = "auto"
            self.control_source_runtime = "runtime"
            self.last_control_reason_runtime = "idle_waiting"
            self.last_control_ts_runtime = utc_now_iso()
            return True
        return False

    def _update_idle_display_state(self) -> None:
        if not self.idle_mode_enabled:
            if self.frontend == "phase1" and self._phase1_idle_episode_consumed:
                return
            if not self.display_mode_active:
                self._enter_display_mode(reason="idle_disabled")
            return
        if self._manual_enter_display_mode:
            self._manual_enter_display_mode = False
            self._enter_display_mode(reason="manual_flag")
            return
        if self.idle_trigger_source == "manual":
            return
        ok, idle_s = self._probe_idle_seconds()
        if ok and idle_s is not None and idle_s < self.idle_seconds:
            self._phase1_idle_episode_consumed = False
            if self.display_mode_active and self.requested_mode == "auto":
                display_reason = str(getattr(self, "display_mode_reason", "") or "")
                if display_reason.endswith("_idle") or display_reason == "idle_disabled":
                    self._exit_display_mode(reason="idle_resumed")
                    return
        if self.display_mode_active:
            return
        now = time.monotonic()
        if now - self._last_idle_wait_log_ts >= 15.0:
            self._last_idle_wait_log_ts = now
            self.log.log(
                "IDLE_WAITING",
                trigger_source=self.idle_trigger_source,
                idle_seconds=self.idle_seconds,
                idle_observed=round(float(idle_s or 0.0), 3),
                idle_probe_ok=ok,
            )
        if not ok or idle_s is None:
            return
        if idle_s >= self.idle_seconds:
            if self._refresh_fullscreen_guard():
                now = time.monotonic()
                if now - self._fullscreen_guard_log_ts >= 15.0:
                    self._fullscreen_guard_log_ts = now
                    self.log.log(
                        "idle_attach_blocked_fullscreen_app",
                        probe=self.fullscreen_guard_probe,
                        windows=self.fullscreen_guard_windows,
                        idle_observed=round(float(idle_s or 0.0), 3),
                        idle_seconds=self.idle_seconds,
                    )
                return
            if self.frontend == "phase1" and self._phase1_idle_episode_consumed:
                return
            if self.frontend == "phase1" and not self.phase1_idle_autorun_enabled:
                if now - self._phase1_idle_autorun_block_log_ts >= 30.0:
                    self._phase1_idle_autorun_block_log_ts = now
                    self.log.log(
                        "phase1_idle_autorun_blocked",
                        reason="phase1_offline_generation_is_manual_only",
                        idle_seconds=self.idle_seconds,
                        idle_observed=round(float(idle_s or 0.0), 3),
                    )
                return
            self._enter_display_mode(reason=f"{self.idle_trigger_source}_idle")

    def _handle_phase1_frontend_completion(self) -> None:
        if self.frontend != "phase1":
            return
        self._sync_frontend_status_from_file()
        if self.display_mode_active and not self.frontend_process_running and not self.frontend_activation_pending:
            completion_reason = ""
            if self.frontend_last_exit_code == 0:
                completion_reason = "phase1_complete"
            elif self.frontend_last_exit_code is not None:
                completion_reason = "phase1_failed"
            elif self.frontend_last_status in {"missing_launcher", "launcher_not_executable", "start_failed"}:
                completion_reason = "phase1_failed"
            if not completion_reason:
                return
            if self.requested_mode == "on":
                self._phase1_requested_mode_on_consumed_ts = self.last_control_ts_runtime
            preview_visible = bool(getattr(getattr(self, "renderer", None), "headless", True) is False)
            if preview_visible:
                self.log.log(
                    "phase1_frontend_complete_preview_continues",
                    reason=completion_reason,
                    requested_mode=self.requested_mode,
                    frontend_last_status=self.frontend_last_status,
                )
                return
            self._exit_display_mode(reason=completion_reason)

    def _renew_gpu_lease(self) -> None:
        if not self._lease_acquired:
            return
        now = time.monotonic()
        renew_every = max(2.0, self.lease_ttl_s * 0.5)
        if (now - self._lease_last_renew_ts) < renew_every:
            return
        ok = self.gpu_lease.renew(owner=self.lease_owner, ttl_s=self.lease_ttl_s)
        self._lease_last_renew_ts = now
        if not ok:
            self.log.log("lease_renew_failed", owner=self.lease_owner, error=self.gpu_lease.last_error)
            if self.lease_mode == "exclusive":
                self.stop_event.set()
                return
        else:
            self.log.log("lease_renewed", owner=self.lease_owner, ttl_s=self.lease_ttl_s)

    def _resolve_gateway_health_urls(self) -> list[str]:
        explicit = str(os.environ.get("OPENCLAW_GATEWAY_HEALTH_URL", "") or "").strip()
        if explicit:
            return [explicit]
        ports: list[int] = []
        for raw in (
            os.environ.get("OPENCLAW_GATEWAY_PORT", ""),
            os.environ.get("OPENCLAW_GATEWAY_HEALTH_PORT", ""),
            "18789",
            "18792",
        ):
            text = str(raw or "").strip()
            if not text:
                continue
            try:
                value = int(text)
            except Exception:
                continue
            if value > 0 and value not in ports:
                ports.append(value)
        return [f"http://127.0.0.1:{port}/health" for port in ports]

    def _probe_gateway_health(self) -> tuple[bool, str]:
        if not self._gateway_health_urls:
            return True, "gateway_health_unknown"
        last_error = "gateway_health_probe_failed"
        for url in self._gateway_health_urls:
            req = urllib.request.Request(url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=0.7) as resp:
                    code = int(getattr(resp, "status", 0) or 0)
            except urllib.error.HTTPError as exc:
                last_error = f"http_{int(exc.code)}@{url}"
                continue
            except Exception as exc:
                last_error = f"{exc.__class__.__name__}@{url}"
                continue
            if 200 <= code < 300:
                return True, url
            last_error = f"http_{code}@{url}"
        return False, last_error

    def _update_load_shed_state(self, telemetry: dict[str, Any]) -> None:
        now = time.monotonic()
        if (now - self._gateway_check_ts) >= 4.0:
            self._gateway_check_ts = now
            self._gateway_ok, self._gateway_reason = self._probe_gateway_health()
        cpu = float(telemetry.get("cpu_load", 0.0) or 0.0)
        gpu = float(telemetry.get("gpu_util", 0.0) or 0.0)
        vram = float(telemetry.get("gpu_vram", 0.0) or 0.0)
        saturated = (cpu >= 0.92) or (gpu >= 0.94) or (vram >= 0.95)
        should_shed = (not self._gateway_ok) and saturated
        if should_shed:
            self._shed_bad_streak = min(12, self._shed_bad_streak + 1)
            self._shed_good_streak = 0
        else:
            self._shed_good_streak = min(12, self._shed_good_streak + 1)
            self._shed_bad_streak = max(0, self._shed_bad_streak - 1)
        if self._shed_bad_streak >= 3:
            reason = f"gateway_unhealthy:{self._gateway_reason};cpu={cpu:.2f};gpu={gpu:.2f};vram={vram:.2f}"
            if reason != self._last_shed_reason or not self.renderer.load_shed_active:
                self.log.log("load_shed_on", reason=reason)
            self._last_shed_reason = reason
            self.renderer.set_load_shed(active=True, reason=reason)
            return
        if self.renderer.load_shed_active and self._shed_good_streak >= 3:
            self.log.log("load_shed_off", reason="gateway_recovered_or_load_normalized")
            self._last_shed_reason = ""
            self.renderer.set_load_shed(active=False, reason="")

    def _process_control_impulses(self) -> None:
        now = time.monotonic()
        if (now - self._last_control_curiosity_ts) < 2.0:
            return
        impulse = self.control_bus.get_value("curiosity_impulse", 0.0)
        if impulse < 0.5:
            return
        self._last_control_curiosity_ts = now
        event = self.curiosity.route(
            query="telegram control bus curiosity impulse",
            response_text="",
            confidence=0.0,
            semantic_match=False,
            reason_code="telegram_control_bus",
            force=True,
            source="telegram_explore",
        )
        self.renderer.inject_curiosity_event(event)
        self._record_telegram_control_event(
            command="/explore",
            controls={"curiosity_impulse": impulse},
            bucket="novelty",
            note="control_bus_impulse",
        )
        self._activity_curiosity_pulse_until = max(self._activity_curiosity_pulse_until, now + 10.0)

    def _compute_activity_snapshot(self, telemetry: dict[str, Any], tacti: dict[str, Any]) -> dict[str, Any]:
        now = time.monotonic()
        active_agents = tacti.get("active_agents", [])
        if not isinstance(active_agents, list):
            active_agents = []
        agent_count = len(active_agents)
        agent_activity = clamp01(min(1.0, agent_count / 6.0))
        research_depth = clamp01(float(tacti.get("research_depth", 0.0) or 0.0))
        token_flux = clamp01(float(tacti.get("token_flux", 0.0) or 0.0))
        memory_recall = clamp01(float(tacti.get("memory_recall_density", 0.0) or 0.0))
        gpu_util = clamp01(float(telemetry.get("gpu_util", 0.0) or 0.0))
        cpu_load = clamp01(float(telemetry.get("cpu_load", telemetry.get("cpu_util", 0.0)) or 0.0))
        curiosity_active = now < float(getattr(self, "_activity_curiosity_pulse_until", 0.0) or 0.0)
        interaction_active = now < float(getattr(self, "_activity_interaction_pulse_until", 0.0) or 0.0)
        active_transient = {}
        try:
            if getattr(self, "control_bus", None) is not None:
                active_transient = dict(self.control_bus.active_transient() or {})
        except Exception:
            active_transient = {}
        curiosity_value = float((active_transient.get("curiosity_impulse") or {}).get("value", 0.0) or 0.0)
        routing_activity = clamp01((research_depth * 0.38) + (token_flux * 0.22) + (agent_activity * 0.16) + (0.16 if curiosity_active else 0.0))
        interaction_activity = clamp01((agent_activity * 0.36) + (0.22 if interaction_active else 0.0) + (curiosity_value * 0.12) + (token_flux * 0.12))
        coordination_density = clamp01((agent_activity * 0.42) + (routing_activity * 0.18) + (interaction_activity * 0.18) + ((1.0 - cpu_load) * 0.08) + ((1.0 - gpu_util) * 0.06))
        memory_activity = clamp01((memory_recall * 0.58) + (research_depth * 0.16) + (0.08 if curiosity_active else 0.0) + (0.08 if interaction_active else 0.0))
        activity_signal = clamp01((agent_activity * 0.24) + (coordination_density * 0.24) + (routing_activity * 0.2) + (interaction_activity * 0.18) + (memory_activity * 0.14))
        heavy_inference_suppressed = bool(getattr(self, "inference_quiesced", False) or getattr(self, "lease_mode", "") == "exclusive")
        if heavy_inference_suppressed and activity_signal < 0.32 and agent_count > 0:
            activity_signal = clamp01(activity_signal + 0.08 + (agent_activity * 0.06))
        summary_parts = [
            f"agent:{agent_activity:.2f}",
            f"coordination:{coordination_density:.2f}",
            f"routing:{routing_activity:.2f}",
            f"interaction:{interaction_activity:.2f}",
        ]
        snapshot = {
            "activity_signal": activity_signal,
            "agent_activity_level": agent_activity,
            "agent_count_active": agent_count,
            "coordination_density": coordination_density,
            "routing_activity": routing_activity,
            "interaction_activity": interaction_activity,
            "memory_activity": memory_activity,
            "heavy_inference_suppressed": heavy_inference_suppressed,
            "semantic_activity_source_summary": ", ".join(summary_parts),
        }
        self.activity_signal = activity_signal
        self.agent_activity_level = agent_activity
        self.agent_count_active = agent_count
        self.coordination_density = coordination_density
        self.routing_activity = routing_activity
        self.interaction_activity = interaction_activity
        self.memory_activity = memory_activity
        self.heavy_inference_suppressed = heavy_inference_suppressed
        self.semantic_activity_source_summary = snapshot["semantic_activity_source_summary"]
        return snapshot

    def _wire_telegram_handlers(self, interface: TelegramCommandInterface) -> None:
        def _capture(command_name: str) -> str:
            telemetry = self._read_json(SYSTEM_PHYSIOLOGY_PATH)
            state = self.renderer.capture_state()
            event_id = self.aesthetic.capture(
                command=command_name,
                renderer_state=state,
                telemetry_snapshot=telemetry,
                camera=state.get("camera", {}),
            )
            self.control_bus.set_transients(
                {
                    "symmetry_bias": 0.85,
                    "mutation_rate": 0.35,
                    "turbulence_boost": 0.25,
                    "temporal_persist": 0.18,
                },
                ttl_seconds=45.0,
            )
            self.control_bus.set_persistent(key="last_capture_hash", value=event_id)
            self.control_bus.set_persistent(key="aesthetic_bias_vector", value=self.aesthetic.bias_vector())
            self._record_telegram_control_event(
                command=command_name,
                controls={"symmetry_bias": 0.85, "mutation_rate": 0.35, "turbulence_boost": 0.25},
                bucket="aesthetic",
                note="capture_with_coherence_window",
            )
            return f"Captured aesthetic state: {event_id}"

        def _more_like_this(arg: str) -> str:
            event_id = arg.strip() or (self.aesthetic.latest_event_id() or "")
            if not event_id:
                return "No capture available yet. Use /capture first."
            score = self.aesthetic.prefer(event_id)
            controls = {"symmetry_bias": 0.9, "mutation_rate": 0.25, "turbulence_boost": 0.2}
            controls["temporal_persist"] = 0.2
            self.control_bus.set_transients(controls, ttl_seconds=60.0)
            self.control_bus.set_persistent(key="aesthetic_bias_vector", value=self.aesthetic.bias_vector())
            self._record_telegram_control_event(
                command="/more-like-this",
                controls=controls,
                bucket="aesthetic",
                note=f"event_id={event_id}",
            )
            return f"Preference applied: {score['event_id']} score={score['score']:.2f}"

        def _explore(arg: str) -> str:
            query = arg.strip() or "explore a hidden mechanism in the current cognition field"
            controls = {"curiosity_impulse": 1.0, "turbulence_boost": 1.2}
            controls["temporal_persist"] = -0.18
            controls["bloom_boost"] = 0.65
            self.control_bus.set_transients(controls, ttl_seconds=10.0)
            event = self.curiosity.route(
                query=query,
                response_text="",
                confidence=0.0,
                semantic_match=False,
                reason_code="telegram_explore",
                force=True,
                source="telegram_explore",
            )
            self.renderer.inject_curiosity_event(event)
            self._record_telegram_control_event(
                command="/explore",
                controls=controls,
                bucket="novelty",
                note=f"seed={event.get('seed', '')}",
            )
            leads = event.get("leads", [])
            if not leads:
                return "Curiosity fired but produced no leads."
            lines = [f"- {item}" for item in leads[:5]]
            return "Curiosity leads:\n" + "\n".join(lines)

        def _boost(arg: str) -> str:
            value, ttl_seconds = self._parse_value_ttl(arg, default_value=1.8, default_seconds=30.0)
            controls = {
                "exposure_boost": max(0.2, min(3.5, value)),
                "density_boost": max(0.5, min(3.0, value)),
                "turbulence_boost": max(0.0, min(2.0, (value - 1.0) * 0.7)),
                "bloom_boost": max(0.0, min(2.0, value * 0.5)),
                "temporal_persist": max(-0.2, min(0.35, (value - 1.0) * 0.15)),
            }
            self.control_bus.set_transients(controls, ttl_seconds=ttl_seconds)
            self._record_telegram_control_event(command="/boost", controls=controls, note=f"ttl={ttl_seconds:.1f}s")
            return f"Boost applied value={value:.2f} ttl={ttl_seconds:.0f}s"

        def _dim(arg: str) -> str:
            value, ttl_seconds = self._parse_value_ttl(arg, default_value=0.75, default_seconds=30.0)
            controls = {
                "exposure_boost": max(0.2, min(1.5, value)),
                "density_boost": max(0.45, min(1.2, value)),
                "turbulence_boost": 0.0,
                "bloom_boost": 0.0,
                "temporal_persist": 0.0,
            }
            self.control_bus.set_transients(controls, ttl_seconds=ttl_seconds)
            self._record_telegram_control_event(command="/dim", controls=controls, note=f"ttl={ttl_seconds:.1f}s")
            return f"Dim applied value={value:.2f} ttl={ttl_seconds:.0f}s"

        def _palette(arg: str) -> str:
            mode = str(arg or "").strip().lower()
            if mode not in {"dusk", "aurora", "roseglass", "ember", "mono"}:
                return f"Usage: /palette dusk|aurora|roseglass|ember|mono (current={self.renderer.palette_mode})"
            self.renderer.set_palette_mode(mode)
            self.control_bus.set_persistent(key="palette_mode", value=mode)
            self._record_telegram_control_event(
                command="/palette",
                controls={"palette_mode_index": float(self.renderer._palette_mode_index())},
                note=f"mode={mode}",
            )
            return f"Palette set: {mode}"

        def _ping(_: str) -> str:
            return self._build_ping_reply()

        def _help(_: str) -> str:
            return "\n".join(
                [
                    "/ping",
                    "/boost [value] [seconds]",
                    "/dim [value] [seconds]",
                    "/more-like-this",
                    "/explore [query]",
                    "/palette dusk|aurora|roseglass|ember|mono",
                    "/beautiful",
                    "/capture",
                ]
            )

        interface.register_handler("/beautiful", lambda _: _capture("/beautiful"))
        interface.register_handler("/capture", lambda _: _capture("/capture"))
        interface.register_handler("/more-like-this", _more_like_this)
        interface.register_handler("/explore", _explore)
        interface.register_handler("/boost", _boost)
        interface.register_handler("/dim", _dim)
        interface.register_handler("/palette", _palette)
        interface.register_handler("/help", _help)
        interface.register_handler("/ping", _ping)

    def _read_ts(self, path: Path) -> str:
        payload = self._read_json(path)
        ts = payload.get("ts")
        if isinstance(ts, str) and ts.strip():
            return ts
        return "missing"

    def _mirror_cathedral_included(self) -> bool:
        try:
            from store.mirror_readers import collect_snapshot

            snapshot = collect_snapshot()
            feeds = snapshot.get("feeds") if isinstance(snapshot, dict) else None
            return isinstance(feeds, dict) and "cathedral_state" in feeds
        except Exception:
            return False

    def _build_ping_reply(self) -> str:
        fishtank_state = self._read_json(FISHTANK_STATE_PATH)
        active_renderer_id = str(fishtank_state.get("active_renderer_id") or self.renderer.active_renderer_id)
        active_renderer_name = str(fishtank_state.get("active_renderer_name") or self.renderer.active_renderer_name)
        gpu_mode = bool(fishtank_state.get("gpu_mode", False))
        fps = float(fishtank_state.get("renderer_fps", 0.0) or 0.0)
        rd_enabled = bool(fishtank_state.get("rd_enabled", False))
        vol_enabled = bool(fishtank_state.get("vol_enabled", False))
        temporal_enabled = bool(fishtank_state.get("temporal_enabled", False))
        tonemap = str(fishtank_state.get("tonemap", "") or "")
        bloom_strength = float(fishtank_state.get("bloom_strength", 0.0) or 0.0)
        exposure_effective = float(fishtank_state.get("exposure_effective", 0.0) or 0.0)
        vol_luminance_mean = float(fishtank_state.get("vol_luminance_mean", 0.0) or 0.0)
        luminance_mean = float(fishtank_state.get("luminance_mean", 0.0) or 0.0)
        luminance_max = float(fishtank_state.get("luminance_max", 0.0) or 0.0)
        clipped_fraction_est = float(fishtank_state.get("clipped_fraction_est", 0.0) or 0.0)
        temporal_alpha = float(fishtank_state.get("temporal_alpha", 0.0) or 0.0)
        palette_mode = str(fishtank_state.get("palette_mode", self.renderer.palette_mode) or self.renderer.palette_mode)
        load_shed_active = bool(fishtank_state.get("load_shed_active", False))
        shed_reason = str(fishtank_state.get("shed_reason", "") or "")
        idle_mode_enabled = bool(fishtank_state.get("idle_mode_enabled", False))
        display_mode_active = bool(fishtank_state.get("display_mode_active", False))
        idle_inhibit_enabled = bool(fishtank_state.get("idle_inhibit_enabled", False))
        display_inhibitor_active = bool(fishtank_state.get("display_inhibitor_active", False))
        inhibitor_backend = str(fishtank_state.get("inhibitor_backend", "none") or "none")
        features_masked = fishtank_state.get("features_masked", [])
        novelty_seed_source = str(fishtank_state.get("novelty_seed_source", "unknown") or "unknown")
        controls = self.control_bus.active_transient()
        controls_json = json.dumps(controls, ensure_ascii=True, sort_keys=True)
        lines = [
            f"host={socket.gethostname()}",
            f"time={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            f"gpu_required={self.renderer.require_gpu}",
            f"display_mode={'headless' if self.renderer.headless else 'windowed'}",
            f"frontend={self.frontend}",
            f"frontend_process_running={self.frontend_process_running}",
            f"frontend_process_pid={self.frontend_process_pid}",
            f"active_renderer_name={active_renderer_name}",
            f"active_renderer_id={active_renderer_id}",
            f"gpu_mode={gpu_mode}",
            f"fps={fps:.2f}",
            f"palette_mode={palette_mode}",
            f"lease_mode={self.lease_mode}",
            f"inference_quiesced={self.inference_quiesced}",
            f"idle_mode_enabled={idle_mode_enabled}",
            f"display_mode_active={display_mode_active}",
            f"idle_inhibit_enabled={idle_inhibit_enabled}",
            f"display_inhibitor_active={display_inhibitor_active}",
            f"inhibitor_backend={inhibitor_backend}",
            f"controls={controls_json}",
            (
                "shader_stack="
                f"rd:{int(rd_enabled)},vol:{int(vol_enabled)},temporal:{int(temporal_enabled)},"
                f"tonemap:{tonemap},exposure:{exposure_effective:.2f},bloom:{bloom_strength:.2f},"
                f"temporal_alpha:{temporal_alpha:.3f},vol_luma:{vol_luminance_mean:.4f},"
                f"luma_mean:{luminance_mean:.4f},luma_max:{luminance_max:.4f},clip_est:{clipped_fraction_est:.4f}"
            ),
            f"gateway_health_ok={self._gateway_ok} gateway_probe={self._gateway_reason}",
            f"load_shed_active={load_shed_active} shed_reason={shed_reason}",
            f"features_masked={features_masked}",
            f"novelty_seed_source={novelty_seed_source}",
            (
                "last_updates="
                f"system_physiology:{self._read_ts(SYSTEM_PHYSIOLOGY_PATH)},"
                f"tacti_state:{self._read_ts(TACTI_STATE_PATH)},"
                f"fishtank_state:{self._read_ts(FISHTANK_STATE_PATH)},"
                f"curiosity_state:{self._read_ts(CURIOSITY_LATEST_PATH)}"
            ),
            f"cathedral_state_in_snapshot={self._mirror_cathedral_included()}",
        ]
        return "\n".join(lines)

    def _read_json(self, path: Path) -> dict[str, Any]:
        payload = load_json(path, {})
        return payload if isinstance(payload, dict) else {}

    def _inference_active(self, telemetry: dict[str, Any], tacti: dict[str, Any]) -> bool:
        if self.inference_quiesced or self.lease_mode == "exclusive":
            return False
        marker = self._read_json(INFERENCE_ACTIVE_PATH)
        if isinstance(marker.get("active"), bool):
            return bool(marker["active"])
        token_flux = float(tacti.get("token_flux", 0.0) or 0.0)
        gpu_util = float(telemetry.get("gpu_util", 0.0) or 0.0)
        return bool(token_flux > 0.45 and gpu_util > 0.65)

    def _dream_gate(self, telemetry: dict[str, Any], tacti: dict[str, Any]) -> bool:
        cpu = float(telemetry.get("cpu_load", 0.0) or 0.0)
        gpu = float(telemetry.get("gpu_util", 0.0) or 0.0)
        flux = 0.0 if (self.inference_quiesced or self.lease_mode == "exclusive") else float(tacti.get("token_flux", 0.0) or 0.0)
        return cpu < 0.35 and gpu < 0.35 and flux < 0.25

    def _apply_aesthetic_bias(self) -> None:
        bias = self.aesthetic.bias_vector()
        blend = 0.04
        for bias_key, shader_key in (
            ("luminosity_bias", "luminosity"),
            ("turbulence_bias", "turbulence"),
            ("velocity_bias", "velocity"),
        ):
            target = float(bias.get(bias_key, 0.0) or 0.0)
            current = float(self.renderer.shader_params.get(shader_key, 0.0) or 0.0)
            self.renderer.shader_params[shader_key] = max(0.0, min(1.0, current * (1.0 - blend) + target * blend))

    def _apply_persistent_overrides(self) -> None:
        persistent = self.control_bus.persistent()
        palette_mode = str(persistent.get("palette_mode", "") or "").strip().lower()
        if palette_mode:
            self.renderer.set_palette_mode(palette_mode)

    def _thread_wrapper(self, *, name: str, target: Any) -> None:
        try:
            target(stop_event=self.stop_event)
        except BaseException as exc:  # pragma: no cover - defensive runtime guard
            self.log.log("background_thread_fatal", thread=name, error=str(exc))
            if self._fatal_error is None:
                self._fatal_error = exc
            self.stop_event.set()

    def _run_telegram_supervisor(self) -> None:
        if self.telegram is None:
            return
        while not self.stop_event.is_set():
            try:
                self.telegram.run_forever(stop_event=self.stop_event)
                if self.stop_event.is_set():
                    return
                if self.telegram_debug_drain:
                    self.log.log("telegram_debug_drain_complete")
                    return
                self.log.log("FATAL_TG", error="telegram_loop_exited", action="restart_in_2s")
            except BaseException as exc:  # pragma: no cover - defensive runtime guard
                self.log.log("FATAL_TG", error=str(exc), action="restart_in_2s")
            time.sleep(2.0)

    def _start_background_threads(self) -> None:
        self._threads = []
        if self.telegram is not None:
            self._threads.append(
                threading.Thread(
                    target=self._run_telegram_supervisor,
                    daemon=True,
                )
            )
        self._threads.extend(
            [
            threading.Thread(
                target=self._thread_wrapper,
                kwargs={"name": "telemetry", "target": self.telemetry.run_forever},
                daemon=True,
            ),
            threading.Thread(
                target=self._thread_wrapper,
                kwargs={"name": "tacti_ingest", "target": self.tacti_ingest.run_forever},
                daemon=True,
            ),
        ]
        )
        for thread in self._threads:
            thread.start()

    def _install_signal_handlers(self) -> None:
        def _handle_signal(signum: int, _frame: Any) -> None:
            self.log.log("runtime_signal", signum=signum)
            self.stop_event.set()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def run(self) -> None:
        self._install_signal_handlers()
        self._start_background_threads()
        period = 1.0 / self.rate_hz
        self.log.log(
            "runtime_start",
            rate_hz=self.rate_hz,
            active_renderer_id=self.renderer.active_renderer_id,
            display_mode=("headless" if self.renderer.headless else "windowed"),
            gpu_required=self.renderer.require_gpu,
        )
        self.log.log(
            "ACTIVE_RENDERER",
            renderer=self.renderer.active_renderer_id,
            display_mode=("headless" if self.renderer.headless else "windowed"),
        )
        next_log = time.monotonic()
        try:
            while not self.stop_event.is_set():
                loop_start = time.monotonic()
                telemetry = self._read_json(SYSTEM_PHYSIOLOGY_PATH)
                tacti = self._read_json(TACTI_STATE_PATH)
                activity_snapshot = self._compute_activity_snapshot(telemetry, tacti)

                self._renew_gpu_lease()
                manual_override_active = self._apply_requested_mode_override()
                if not manual_override_active:
                    self._update_idle_display_state()
                self.renderer.allow_visible_attach = bool(
                    self.frontend != "python"
                    or not self.idle_mode_enabled
                    or self.python_visible_attach_enabled
                )
                try:
                    self.renderer.set_runtime_context(
                        lease_mode=self.lease_mode,
                        inference_quiesced=self.inference_quiesced,
                        idle_mode_enabled=self.idle_mode_enabled,
                        idle_trigger_source=self.idle_trigger_source,
                        idle_triggered_at=self.idle_triggered_at,
                        display_mode_active=self.display_mode_active,
                        idle_inhibit_enabled=self.idle_inhibit_enabled,
                        display_inhibitor_active=self.display_inhibitor_active,
                        inhibitor_backend=self.inhibitor_backend,
                    )
                except Exception as exc:
                    if self.frontend == "python" and self.display_mode_active:
                        self.log.log(
                            "DISPLAY_MODE_ATTACH_FAILED",
                            error=str(exc),
                            display=str(os.environ.get("DISPLAY", "") or ""),
                            xauthority=str(os.environ.get("XAUTHORITY", "") or ""),
                        )
                        self.python_visible_attach_enabled = False
                        self.renderer.allow_visible_attach = False
                        self._exit_display_mode(reason="python_attach_failed")
                        self.renderer.set_runtime_context(
                            lease_mode=self.lease_mode,
                            inference_quiesced=self.inference_quiesced,
                            idle_mode_enabled=self.idle_mode_enabled,
                            idle_trigger_source=self.idle_trigger_source,
                            idle_triggered_at=self.idle_triggered_at,
                            display_mode_active=self.display_mode_active,
                            idle_inhibit_enabled=self.idle_inhibit_enabled,
                            display_inhibitor_active=self.display_inhibitor_active,
                            inhibitor_backend=self.inhibitor_backend,
                        )
                    else:
                        raise
                if self.display_mode_active and self.frontend in {"ue5", "phase1"}:
                    self._start_frontend()
                else:
                    self._sync_frontend_state()
                if self.frontend == "phase1":
                    self._handle_phase1_frontend_completion()
                self.renderer.activity_snapshot = activity_snapshot
                if not self.display_mode_active:
                    self.renderer.update_signals(telemetry, tacti)
                    self.renderer.set_inference_active(self._inference_active(telemetry, tacti))
                    state = self._state_payload(self.renderer.capture_state())
                    state["frame"] = self.renderer.frame_index
                    atomic_write_json(FISHTANK_STATE_PATH, state)
                    now = time.monotonic()
                    if now >= next_log:
                        self.log.log(
                            "runtime_frame",
                            frame=state.get("frame"),
                            gpu_mode=state.get("gpu_mode"),
                            inference_active=state.get("inference_active"),
                            display_mode_active=False,
                        )
                        next_log = now + 5.0
                    elapsed = time.monotonic() - loop_start
                    sleep_for = period - elapsed
                    if sleep_for > 0:
                        time.sleep(sleep_for)
                    continue
                self.renderer.update_signals(telemetry, tacti)
                self.renderer.set_inference_active(self._inference_active(telemetry, tacti))
                self._update_load_shed_state(telemetry)
                self._apply_persistent_overrides()
                self._apply_aesthetic_bias()
                self._process_control_impulses()

                if self._dream_gate(telemetry, tacti):
                    if (time.monotonic() - self.renderer.last_dream_ts) > 8.0:
                        self.renderer.dream_cycle()
                        self.renderer.last_dream_ts = time.monotonic()

                state = self._state_payload(self.renderer.tick())
                atomic_write_json(FISHTANK_STATE_PATH, state)
                now = time.monotonic()
                if now >= next_log:
                    self.log.log(
                        "runtime_frame",
                        frame=state.get("frame"),
                        gpu_mode=state.get("gpu_mode"),
                        inference_active=state.get("inference_active"),
                        display_mode_active=True,
                    )
                    next_log = now + 5.0

                elapsed = time.monotonic() - loop_start
                sleep_for = period - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            self._exit_display_mode(reason="shutdown")
            if self.renderer is not None:
                self.renderer.close()
            self._stop_frontend()
            self._unquiesce_inference_mode()
            if self._lease_acquired:
                released = self.gpu_lease.release(owner=self.lease_owner)
                self.log.log("lease_released", owner=self.lease_owner, released=released, lease_file=str(GPU_LEASE_PATH))

        if self._fatal_error is not None:
            self.log.log("runtime_stop", fatal_error=str(self._fatal_error))
            raise RuntimeError(f"background thread failed: {self._fatal_error}") from self._fatal_error
        self.log.log("runtime_stop")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DALI Consciousness Mirror runtime")
    parser.add_argument("--rate-hz", type=float, default=float(os.environ.get("DALI_FISHTANK_RATE_HZ", "30")))
    parser.add_argument(
        "--telemetry-hz", type=float, default=float(os.environ.get("DALI_FISHTANK_TELEMETRY_HZ", "6"))
    )
    parser.add_argument("--tacti-hz", type=float, default=float(os.environ.get("DALI_FISHTANK_TACTI_HZ", "2")))
    parser.add_argument(
        "--agent-count", type=int, default=int(os.environ.get("DALI_FISHTANK_AGENT_COUNT", "120000"))
    )
    parser.add_argument("--headless", action="store_true", default=os.environ.get("DALI_FISHTANK_HEADLESS", "0") == "1")
    parser.add_argument(
        "--require-gpu",
        action="store_true",
        default=os.environ.get("DALI_FISHTANK_REQUIRE_GPU", "1") == "1",
    )
    parser.add_argument(
        "--enter-display-mode",
        action="store_true",
        default=os.environ.get("DALI_FISHTANK_ENTER_DISPLAY_MODE", "0") == "1",
        help="Force immediate display mode entry without waiting for idle trigger.",
    )
    return parser


def _log_runtime_env_summary() -> None:
    logger = JsonlLogger(RUNTIME_LOGS / "dali_cathedral_runtime.log")
    enabled_raw = os.environ.get("DALI_FISHTANK_TELEGRAM_ENABLED", "")
    telegram_enabled_default_on = enabled_raw != "0"
    env_file = Path.home() / ".config" / "openclaw" / "dali-fishtank.env"
    logger.log(
        "runtime_env_summary",
        env_file=str(env_file),
        env_file_exists=env_file.exists(),
        has_rate_hz=("DALI_FISHTANK_RATE_HZ" in os.environ),
        has_headless=("DALI_FISHTANK_HEADLESS" in os.environ),
        has_require_gpu=("DALI_FISHTANK_REQUIRE_GPU" in os.environ),
        lease_mode=str(os.environ.get("DALI_FISHTANK_GPU_LEASE_MODE", "exclusive") or "exclusive"),
        lease_ttl_s=float(os.environ.get("DALI_FISHTANK_GPU_LEASE_TTL_S", "20") or 20.0),
        quiesce_enabled=str(os.environ.get("DALI_FISHTANK_QUIESCE_INFERENCE", "1") or "1"),
        quiesce_units=str(os.environ.get("DALI_FISHTANK_QUIESCE_UNITS", "") or ""),
        quiesce_endpoint_set=bool(str(os.environ.get("DALI_FISHTANK_QUIESCE_ENDPOINT", "") or "").strip()),
        idle_enable=str(os.environ.get("DALI_FISHTANK_IDLE_ENABLE", "1") or "1"),
        idle_seconds=float(os.environ.get("DALI_FISHTANK_IDLE_SECONDS", "300") or 300.0),
        idle_inhibit=str(os.environ.get("DALI_FISHTANK_IDLE_INHIBIT", "1") or "1"),
        idle_trigger_source=str(os.environ.get("DALI_FISHTANK_IDLE_TRIGGER_SOURCE", "internal") or "internal"),
        telegram_enabled=telegram_enabled_default_on,
        telegram_enabled_raw=enabled_raw,
        telegram_required=str(os.environ.get("DALI_FISHTANK_TELEGRAM_REQUIRED", "0") or "0"),
        telegram_token_present=bool((os.environ.get("DALI_FISHTANK_TELEGRAM_TOKEN", "") or "").strip()),
        telegram_allowlist_present=bool((os.environ.get("DALI_FISHTANK_TELEGRAM_ALLOWLIST", "") or "").strip()),
        telegram_debug_drain=(os.environ.get("DALI_FISHTANK_TELEGRAM_DEBUG_DRAIN", "0") == "1"),
        frontend=str(os.environ.get("DALI_FISHTANK_FRONTEND", "python") or "python"),
        ue5_launcher=str(os.environ.get("DALI_FISHTANK_UE5_LAUNCHER", "") or ""),
        phase1_launcher=str(os.environ.get("DALI_FISHTANK_PHASE1_LAUNCHER", "") or ""),
        phase1_status_path=str(os.environ.get("DALI_FISHTANK_PHASE1_STATUS_PATH", "") or ""),
    )


def _resolve_telegram_config() -> dict[str, Any]:
    logger = JsonlLogger(RUNTIME_LOGS / "dali_cathedral_runtime.log")
    env_file = Path.home() / ".config" / "openclaw" / "dali-fishtank.env"
    token = os.environ.get("DALI_FISHTANK_TELEGRAM_TOKEN", "")
    enabled_raw = os.environ.get("DALI_FISHTANK_TELEGRAM_ENABLED", "")
    enabled_requested = enabled_raw != "0"
    autoclear_webhook = os.environ.get("DALI_FISHTANK_TELEGRAM_AUTOCLEAR_WEBHOOK", "0") == "1"
    debug_drain = os.environ.get("DALI_FISHTANK_TELEGRAM_DEBUG_DRAIN", "0") == "1"
    allowlist_raw = os.environ.get("DALI_FISHTANK_TELEGRAM_ALLOWLIST", "")
    allowlist = [item.strip() for item in allowlist_raw.split(",") if item.strip()]
    missing_keys: list[str] = []
    if not token.strip():
        missing_keys.append("DALI_FISHTANK_TELEGRAM_TOKEN")
    if not allowlist:
        missing_keys.append("DALI_FISHTANK_TELEGRAM_ALLOWLIST")

    enabled_effective = bool(enabled_requested and not missing_keys)
    logger.log(
        "telegram_runtime_config",
        message=(
            f"telegram: enabled={1 if enabled_requested else 0} "
            f"token_present={1 if bool(token.strip()) else 0} "
            f"chat_present={1 if bool(allowlist) else 0}"
        ),
        enabled_requested=enabled_requested,
        enabled_effective=enabled_effective,
        token_present=bool(token.strip()),
        chat_present=bool(allowlist),
        env_file=str(env_file),
    )
    if enabled_requested and not enabled_effective:
        logger.log(
            "telegram_disabled_missing_env",
            token_present=bool(token.strip()),
            chat_id_present=bool(allowlist),
            enabled_flag=enabled_requested,
            missing_keys=missing_keys,
            env_file=str(env_file),
        )
        print(
            (
                "LOCAL_PING telegram_misconfigured "
                f"env_file={env_file} missing_keys={','.join(missing_keys)} "
                "renderer_continues=true"
            ),
            flush=True,
        )
    elif enabled_effective:
        logger.log(
            "telegram_enabled_config",
            token_present=True,
            chat_id_count=len(allowlist),
            debug_drain=debug_drain,
            autoclear_webhook=autoclear_webhook,
        )
    else:
        logger.log("telegram_disabled_by_env")

    return {
        "enabled_requested": enabled_requested,
        "enabled_effective": enabled_effective,
        "token": token,
        "allowlist": allowlist,
        "autoclear_webhook": autoclear_webhook,
        "debug_drain": debug_drain,
        "missing_keys": missing_keys,
        "env_file": str(env_file),
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _log_runtime_env_summary()
    telegram_config = _resolve_telegram_config()

    runtime = DaliCathedralRuntime(
        rate_hz=args.rate_hz,
        telemetry_hz=args.telemetry_hz,
        tacti_hz=args.tacti_hz,
        agent_count=args.agent_count,
        headless=bool(args.headless),
        require_gpu=bool(args.require_gpu),
        telegram_enabled=bool(telegram_config["enabled_effective"]),
        telegram_token=str(telegram_config["token"]),
        telegram_allowlist=list(telegram_config["allowlist"]),
        telegram_autoclear_webhook=bool(telegram_config["autoclear_webhook"]),
        telegram_debug_drain=bool(telegram_config["debug_drain"]),
        telegram_requested=bool(telegram_config["enabled_requested"]),
        telegram_missing_keys=list(telegram_config["missing_keys"]),
        telegram_env_file=str(telegram_config["env_file"]),
        enter_display_mode=bool(args.enter_display_mode),
    )
    runtime.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
