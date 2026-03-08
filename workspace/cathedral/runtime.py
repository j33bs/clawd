from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import signal
import threading
import time
from pathlib import Path
from typing import Any

from .aesthetic_feedback import AestheticFeedbackStore
from .control_bus import ControlBus
from .curiosity_router import CuriosityRouter
from .fishtank_renderer import FishTankRenderer
from .io_utils import append_jsonl, load_json, utc_now_iso
from .logging_utils import JsonlLogger
from .paths import (
    AESTHETIC_EVENTS_DIR,
    CURIOSITY_LATEST_PATH,
    FISHTANK_STATE_PATH,
    NOVELTY_ARCHIVE_DIR,
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
    ):
        ensure_runtime_dirs()
        self.rate_hz = max(1.0, float(rate_hz))
        self.stop_event = threading.Event()
        self.log = JsonlLogger(RUNTIME_LOGS / "dali_cathedral_runtime.log")
        self._fatal_error: BaseException | None = None

        self.telemetry = TelemetryDaemon(rate_hz=telemetry_hz)
        self.tacti_ingest = TactiStateIngestor(rate_hz=tacti_hz)
        self.curiosity = CuriosityRouter()
        self.control_bus = ControlBus()
        self.renderer = FishTankRenderer(
            agent_count=agent_count,
            headless=headless,
            require_gpu=require_gpu,
            control_bus=self.control_bus,
        )
        self.aesthetic = AestheticFeedbackStore()
        self.telegram_requested = bool(telegram_requested)
        self.telegram_debug_drain = bool(telegram_debug_drain)
        self.telegram_missing_keys = list(telegram_missing_keys or [])
        self.telegram_env_file = str(telegram_env_file or "")
        self._last_control_curiosity_ts = 0.0

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
        consumer = str(os.environ.get("DALI_FISHTANK_HEADLESS_CONSUMER", "") or "").strip()
        if consumer:
            self.log.log("renderer_display_mode", mode="headless", headless_consumer=consumer)
            return
        self.log.log(
            "headless_no_display_warning",
            message="HEADLESS=1 with no downstream consumer; nothing will appear on screen",
        )

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
        temporal_alpha = float(fishtank_state.get("temporal_alpha", 0.0) or 0.0)
        controls = self.control_bus.active_transient()
        controls_json = json.dumps(controls, ensure_ascii=True, sort_keys=True)
        lines = [
            f"host={socket.gethostname()}",
            f"time={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            f"gpu_required={self.renderer.require_gpu}",
            f"display_mode={'headless' if self.renderer.headless else 'windowed'}",
            f"active_renderer_name={active_renderer_name}",
            f"active_renderer_id={active_renderer_id}",
            f"gpu_mode={gpu_mode}",
            f"fps={fps:.2f}",
            f"controls={controls_json}",
            (
                "shader_stack="
                f"rd:{int(rd_enabled)},vol:{int(vol_enabled)},temporal:{int(temporal_enabled)},"
                f"tonemap:{tonemap},exposure:{exposure_effective:.2f},bloom:{bloom_strength:.2f},"
                f"temporal_alpha:{temporal_alpha:.3f},vol_luma:{vol_luminance_mean:.4f}"
            ),
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
        marker = self._read_json(INFERENCE_ACTIVE_PATH)
        if isinstance(marker.get("active"), bool):
            return bool(marker["active"])
        token_flux = float(tacti.get("token_flux", 0.0) or 0.0)
        gpu_util = float(telemetry.get("gpu_util", 0.0) or 0.0)
        return bool(token_flux > 0.45 and gpu_util > 0.65)

    def _dream_gate(self, telemetry: dict[str, Any], tacti: dict[str, Any]) -> bool:
        cpu = float(telemetry.get("cpu_load", 0.0) or 0.0)
        gpu = float(telemetry.get("gpu_util", 0.0) or 0.0)
        flux = float(tacti.get("token_flux", 0.0) or 0.0)
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

        while not self.stop_event.is_set():
            loop_start = time.monotonic()
            telemetry = self._read_json(SYSTEM_PHYSIOLOGY_PATH)
            tacti = self._read_json(TACTI_STATE_PATH)

            self.renderer.update_signals(telemetry, tacti)
            self.renderer.set_inference_active(self._inference_active(telemetry, tacti))
            self._apply_aesthetic_bias()
            self._process_control_impulses()

            if self._dream_gate(telemetry, tacti):
                if (time.monotonic() - self.renderer.last_dream_ts) > 8.0:
                    self.renderer.dream_cycle()
                    self.renderer.last_dream_ts = time.monotonic()

            state = self.renderer.tick()
            now = time.monotonic()
            if now >= next_log:
                self.log.log(
                    "runtime_frame",
                    frame=state.get("frame"),
                    gpu_mode=state.get("gpu_mode"),
                    inference_active=state.get("inference_active"),
                )
                next_log = now + 5.0

            elapsed = time.monotonic() - loop_start
            sleep_for = period - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

        self.renderer.close()
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
        telegram_enabled=telegram_enabled_default_on,
        telegram_enabled_raw=enabled_raw,
        telegram_token_present=bool((os.environ.get("DALI_FISHTANK_TELEGRAM_TOKEN", "") or "").strip()),
        telegram_allowlist_present=bool((os.environ.get("DALI_FISHTANK_TELEGRAM_ALLOWLIST", "") or "").strip()),
        telegram_debug_drain=(os.environ.get("DALI_FISHTANK_TELEGRAM_DEBUG_DRAIN", "0") == "1"),
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
    )
    runtime.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
