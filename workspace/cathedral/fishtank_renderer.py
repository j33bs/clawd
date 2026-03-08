from __future__ import annotations

import json
import math
import os
import random
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_json, clamp01, load_json, safe_float, utc_now_iso
from .logging_utils import JsonlLogger
from .paths import DREAM_STATES_DIR, FISHTANK_STATE_PATH, RUNTIME_LOGS, ensure_runtime_dirs

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

try:
    import glfw  # type: ignore
    import moderngl  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    glfw = None
    moderngl = None


@dataclass
class RendererSignals:
    arousal: float = 0.5
    gpu_util: float = 0.0
    gpu_vram: float = 0.0
    gpu_vram_used_mb: float = 0.0
    cpu_temp: float = 50.0
    fan_speed: float = 1200.0
    disk_io: float = 0.0
    memory_density: float = 0.0


class GPUUnavailableError(RuntimeError):
    """Raised when GPU rendering is required but unavailable."""


SHADER_ERROR_LOG_PATH = RUNTIME_LOGS / "fishtank_shader_errors.log"


def _env_truthy(name: str, default: str = "0") -> bool:
    value = str(os.environ.get(name, default) or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def aces_filmic_fit(value: float) -> float:
    # Narkowicz ACES fit for a perceptual, non-clipping rolloff.
    x = max(0.0, float(value))
    a = 2.51
    b = 0.03
    c = 2.43
    d = 0.59
    e = 0.14
    return max(0.0, min(1.0, (x * (a * x + b)) / (x * (c * x + d) + e)))


def _git_short_sha() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except Exception:
        return "unknown"
    if proc.returncode != 0:
        return "unknown"
    value = str(proc.stdout or "").strip()
    return value or "unknown"


class FishTankRenderer:
    """
    GPU-aware emergent renderer.

    - GPU path: moderngl compute + point cloud raster.
    - CPU fallback: numpy flock field (still emergent and telemetry-driven).
    """

    def __init__(
        self,
        *,
        agent_count: int = 120_000,
        width: int = 1280,
        height: int = 720,
        headless: bool = False,
        require_gpu: bool = True,
        control_bus: Any | None = None,
        output_path: Path = FISHTANK_STATE_PATH,
    ):
        ensure_runtime_dirs()
        self.output_path = output_path
        self.width = int(width)
        self.height = int(height)
        self.headless = bool(headless)
        self.require_gpu = bool(require_gpu)
        self.agent_count = max(150_000, min(1_000_000, int(agent_count)))
        self.log = JsonlLogger(RUNTIME_LOGS / "fishtank_renderer.log")
        self.control_bus = control_bus
        self.signals = RendererSignals()
        self.curiosity_impulses: list[dict[str, Any]] = []
        self.inference_active = False
        self.last_frame_ts = time.monotonic()
        self.frame_index = 0
        self.last_dream_ts = 0.0
        self.gpu_mode = False
        self.backend = "none"
        self.renderer_fps = 0.0
        self.last_frame_ms = 0.0
        self.fb_w = 0
        self.fb_h = 0
        self._last_gl_error_ts = 0.0
        self.active_renderer_name = "cathedral_fishtank"
        self.active_renderer_version = _git_short_sha()
        self.active_renderer_id = f"{self.active_renderer_name}:{self.active_renderer_version}"
        self.exposure_base = max(0.2, min(4.0, safe_float(os.environ.get("DALI_FISHTANK_EXPOSURE_BASE", 1.6), 1.6)))
        bloom_raw = str(os.environ.get("DALI_FISHTANK_BLOOM", "1") or "1").strip()
        self.bloom_enabled = bloom_raw not in {"0", "false", "off", "no"}
        bloom_default = 0.6 if self.bloom_enabled else 0.0
        self.bloom_strength = max(
            0.0,
            min(
                2.0,
                safe_float(
                    os.environ.get("DALI_FISHTANK_BLOOM_STRENGTH", os.environ.get("DALI_FISHTANK_BLOOM", bloom_default)),
                    bloom_default,
                ),
            ),
        )
        self.contrast_base = max(0.5, min(2.5, safe_float(os.environ.get("DALI_FISHTANK_CONTRAST", 1.2), 1.2)))
        self.saturation_base = max(0.3, min(2.5, safe_float(os.environ.get("DALI_FISHTANK_SATURATION", 1.2), 1.2)))
        self.tonemap_mode = str(os.environ.get("DALI_FISHTANK_TONEMAP", "aces") or "aces").strip().lower()
        self.rd_enabled = _env_truthy("DALI_FISHTANK_RD_ENABLED", "1")
        self.vol_enabled = _env_truthy("DALI_FISHTANK_VOL_ENABLED", "1")
        self.temporal_enabled = _env_truthy("DALI_FISHTANK_TEMPORAL_ENABLED", "1")
        self.rd_res = max(128, min(2048, int(safe_float(os.environ.get("DALI_FISHTANK_RD_RES", 768), 768))))
        self.rd_hz = max(1.0, min(120.0, safe_float(os.environ.get("DALI_FISHTANK_RD_HZ", 30.0), 30.0)))
        self.rd_feed_base = max(0.001, min(0.12, safe_float(os.environ.get("DALI_FISHTANK_RD_FEED", 0.0367), 0.0367)))
        self.rd_kill_base = max(0.001, min(0.12, safe_float(os.environ.get("DALI_FISHTANK_RD_KILL", 0.0649), 0.0649)))
        self.rd_du_base = max(0.01, min(2.0, safe_float(os.environ.get("DALI_FISHTANK_RD_DU", 0.16), 0.16)))
        self.rd_dv_base = max(0.01, min(2.0, safe_float(os.environ.get("DALI_FISHTANK_RD_DV", 0.08), 0.08)))
        self.rd_dt_base = max(0.1, min(3.0, safe_float(os.environ.get("DALI_FISHTANK_RD_DT", 1.0), 1.0)))
        self.rd_feed = float(self.rd_feed_base)
        self.rd_kill = float(self.rd_kill_base)
        self.rd_du = float(self.rd_du_base)
        self.rd_dv = float(self.rd_dv_base)
        self.rd_dt = float(self.rd_dt_base)
        self.vol_steps = max(12, min(192, int(safe_float(os.environ.get("DALI_FISHTANK_VOL_STEPS", 48), 48))))
        self.temporal_alpha_base = max(
            0.2,
            min(0.99, safe_float(os.environ.get("DALI_FISHTANK_TEMPORAL_ALPHA", 0.92), 0.92)),
        )
        self.temporal_alpha = float(self.temporal_alpha_base)
        self.vol_luminance_mean = 0.0
        self._motion_scalar = 0.0
        self._last_rd_step_ts = time.monotonic()
        self._rd_inject_until = 0.0
        self._rd_inject_seed = 0.0
        self._rd_mutation = random.Random()
        self._last_control_file_ts = 0.0
        self._control_file_cache: dict[str, dict[str, float]] = {}

        self.particles_target = int(
            min(
                self.agent_count,
                max(150_000, int(safe_float(os.environ.get("DALI_FISHTANK_PARTICLES_TARGET", self.agent_count)))),
            )
        )
        self.particles_visible = int(self.particles_target)
        self.controls_snapshot: dict[str, dict[str, float]] = {}
        self.control_values: dict[str, float] = {
            "exposure_boost": 1.0,
            "density_boost": 1.0,
            "turbulence_boost": 0.0,
            "symmetry_bias": 0.0,
            "curiosity_impulse": 0.0,
            "mutation_rate": 1.0,
            "bloom_boost": 0.0,
            "temporal_persist": 0.0,
        }
        self.effective_exposure = self.exposure_base
        self.effective_bloom = self.bloom_strength
        self.effective_contrast = self.contrast_base
        self.effective_saturation = self.saturation_base
        self._curiosity_pulse_until = 0.0

        self.shader_params = {
            "luminosity": 0.5,
            "turbulence": 0.4,
            "velocity": 0.4,
            "warmth": 0.4,
            "vortex": 0.3,
            "ripple": 0.2,
            "cloud": 0.2,
            "nebula": 0.3,
        }

        self._ctx = None
        self._window = None
        self._prog = None
        self._compute = None
        self._quad = None
        self._quad_vbo = None
        self._rd_prog = None
        self._vol_prog = None
        self._temporal_prog = None
        self._copy_prog = None
        self._bloom_extract_prog = None
        self._blur_prog = None
        self._tonemap_prog = None
        self._rd_tex_a = None
        self._rd_tex_b = None
        self._rd_fbo_a = None
        self._rd_fbo_b = None
        self._rd_dummy_tex = None
        self._rd_ping = 0
        self._scene_tex = None
        self._scene_fbo = None
        self._temporal_tex_a = None
        self._temporal_tex_b = None
        self._temporal_fbo_a = None
        self._temporal_fbo_b = None
        self._temporal_ping = 0
        self._bloom_tex_a = None
        self._bloom_tex_b = None
        self._bloom_fbo_a = None
        self._bloom_fbo_b = None
        self._post_w = 0
        self._post_h = 0

        self._init_particle_state()
        self._init_gpu_backend()
        if self.require_gpu and not self.gpu_mode:
            raise GPUUnavailableError("GPU mode required but initialization failed")
        self.log.log(
            "fishtank_init",
            agent_count=self.agent_count,
            gpu_mode=self.gpu_mode,
            headless=self.headless,
            backend=self.backend,
            require_gpu=self.require_gpu,
            active_renderer_id=self.active_renderer_id,
            exposure_base=self.exposure_base,
            particles_target=self.particles_target,
        )

    def _init_particle_state(self) -> None:
        if np is None:
            if self.require_gpu:
                raise GPUUnavailableError("numpy is required for GPU particle buffers")
            self.positions = [[random.uniform(-1.0, 1.0), random.uniform(-1.0, 1.0)] for _ in range(20_000)]
            self.velocities = [[0.0, 0.0] for _ in range(20_000)]
            self.agent_count = len(self.positions)
            return
        rng = np.random.default_rng(42)
        self.positions = rng.uniform(-1.0, 1.0, size=(self.agent_count, 2)).astype("float32")
        self.velocities = rng.normal(0.0, 0.01, size=(self.agent_count, 2)).astype("float32")

    def _append_shader_error(self, stage: str, source_label: str, exc: BaseException) -> None:
        payload = {
            "ts": utc_now_iso(),
            "stage": stage,
            "source": source_label,
            "error": str(exc),
        }
        with SHADER_ERROR_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")
        self.log.log("shader_compile_failed", stage=stage, error=str(exc))

    def _query_framebuffer_size(self) -> tuple[int, int]:
        if self._window is None or glfw is None:
            return self.fb_w, self.fb_h
        try:
            width, height = glfw.get_framebuffer_size(self._window)
            self.fb_w = int(width)
            self.fb_h = int(height)
        except Exception:
            self.fb_w = 0
            self.fb_h = 0
        return self.fb_w, self.fb_h

    def _ensure_nonzero_framebuffer(self) -> None:
        width, height = self._query_framebuffer_size()
        if width > 0 and height > 0:
            return
        raise GPUUnavailableError(f"invalid framebuffer size: {width}x{height}")

    def _present_first_frame_sentinel(self) -> None:
        if self._window is None or glfw is None or self._ctx is None:
            return
        glfw.make_context_current(self._window)
        self._ensure_nonzero_framebuffer()
        self._ctx.viewport = (0, 0, self.fb_w, self.fb_h)
        self._ctx.clear(0.05, 0.05, 0.08, 1.0)
        glfw.swap_buffers(self._window)
        glfw.poll_events()
        self.log.log("first_frame_sentinel_presented", fb_w=self.fb_w, fb_h=self.fb_h)

    def _check_gl_error(self) -> None:
        if self._ctx is None:
            return
        try:
            err = str(self._ctx.error)
        except Exception:
            return
        if err == "GL_NO_ERROR":
            return
        now = time.monotonic()
        if now - self._last_gl_error_ts < 5.0:
            return
        self._last_gl_error_ts = now
        self.log.log("gl_error", error=err)

    def _refresh_control_values(self) -> None:
        def _coerce_controls(payload: Any) -> dict[str, dict[str, float]]:
            out: dict[str, dict[str, float]] = {}
            if not isinstance(payload, dict):
                return out
            for key, row in payload.items():
                if not isinstance(row, dict):
                    continue
                out[str(key)] = {
                    "value": safe_float(row.get("value", 0.0), 0.0),
                    "ttl_s": max(0.0, safe_float(row.get("ttl_s", 0.0), 0.0)),
                }
            return out

        if self.control_bus is None:
            live_controls = {}
        else:
            live_controls = _coerce_controls(self.control_bus.active_transient())

        now = time.monotonic()
        if (now - self._last_control_file_ts) >= 0.4 and self.control_bus is not None:
            self._last_control_file_ts = now
            try:
                payload = load_json(Path(getattr(self.control_bus, "state_path")), {})
                from_file = _coerce_controls(payload.get("active_transient", {}))
            except Exception:
                from_file = {}
            self._control_file_cache = from_file
        merged_controls = dict(self._control_file_cache)
        for key, row in live_controls.items():
            prev = merged_controls.get(key, {})
            if row.get("ttl_s", 0.0) >= prev.get("ttl_s", 0.0):
                merged_controls[key] = row
        self.controls_snapshot = merged_controls

        def _value(name: str, default: float) -> float:
            row = self.controls_snapshot.get(name)
            if not isinstance(row, dict):
                return float(default)
            return float(row.get("value", default))

        self.control_values = {
            "exposure_boost": max(0.2, min(3.5, _value("exposure_boost", 1.0))),
            "density_boost": max(0.4, min(3.0, _value("density_boost", 1.0))),
            "turbulence_boost": max(0.0, min(2.0, _value("turbulence_boost", 0.0))),
            "symmetry_bias": max(0.0, min(1.0, _value("symmetry_bias", 0.0))),
            "curiosity_impulse": max(0.0, min(1.5, _value("curiosity_impulse", 0.0))),
            "mutation_rate": max(0.2, min(2.0, _value("mutation_rate", 1.0))),
            "bloom_boost": max(0.0, min(2.0, _value("bloom_boost", 0.0))),
            "temporal_persist": max(-0.5, min(0.5, _value("temporal_persist", 0.0))),
        }

        if self.control_values["curiosity_impulse"] >= 0.5:
            self._curiosity_pulse_until = max(self._curiosity_pulse_until, now + 1.0)
            self._rd_inject_until = max(self._rd_inject_until, now + 1.7)
            self._rd_inject_seed = now
        curiosity_pulse = max(0.0, self._curiosity_pulse_until - now)
        impulse_norm = max(0.0, min(1.0, curiosity_pulse))

        self.effective_exposure = self.exposure_base * self.control_values["exposure_boost"]
        boost_n = max(0.0, self.control_values["exposure_boost"] - 1.0)
        self.effective_bloom = (
            self.bloom_strength
            + (0.55 * curiosity_pulse)
            + (0.5 * boost_n)
            + (0.4 * self.control_values["bloom_boost"])
        )
        if not self.bloom_enabled:
            self.effective_bloom = 0.0
        self.effective_contrast = self.contrast_base + (0.35 * curiosity_pulse)
        self.effective_saturation = self.saturation_base + (0.3 * curiosity_pulse)
        self.temporal_alpha = max(
            0.55,
            min(
                0.985,
                self.temporal_alpha_base
                - (0.12 * impulse_norm)
                + (0.02 * boost_n)
                + (0.05 * self.control_values["temporal_persist"]),
            ),
        )

        density_target = int(self.particles_target * self.control_values["density_boost"])
        density_target = max(150_000, min(self.agent_count, density_target))
        self.particles_visible = int((self.particles_visible * 0.65) + (density_target * 0.35))
        self.particles_visible = max(150_000, min(self.agent_count, self.particles_visible))

        self.shader_params["luminosity"] = clamp01(self.shader_params["luminosity"] * min(2.0, self.effective_exposure))
        self.shader_params["turbulence"] = clamp01(
            self.shader_params["turbulence"]
            + (0.35 * self.control_values["turbulence_boost"])
            - (0.25 * self.control_values["symmetry_bias"])
            + (0.5 * curiosity_pulse)
        )
        self.shader_params["vortex"] = clamp01(
            self.shader_params["vortex"] + (0.45 * self.control_values["symmetry_bias"]) + (0.35 * curiosity_pulse)
        )
        self.shader_params["cloud"] = clamp01(self.shader_params["cloud"] + (0.2 * self.control_values["symmetry_bias"]))
        self._motion_scalar = clamp01(
            0.45 * self.shader_params["velocity"]
            + 0.35 * self.shader_params["turbulence"]
            + 0.2 * self.control_values["curiosity_impulse"]
        )

        coherence = self.control_values["symmetry_bias"]
        mutation = self.control_values["mutation_rate"]
        beautiful_bias = clamp01(coherence * (2.0 - mutation))
        self.rd_feed = max(0.002, min(0.12, self.rd_feed_base + 0.015 * self.control_values["turbulence_boost"] - 0.008 * beautiful_bias))
        self.rd_kill = max(0.002, min(0.12, self.rd_kill_base + 0.01 * beautiful_bias - 0.005 * self.control_values["turbulence_boost"]))
        self.rd_du = max(0.01, min(2.0, self.rd_du_base + 0.2 * beautiful_bias))
        self.rd_dv = max(0.01, min(2.0, self.rd_dv_base + 0.08 * self.control_values["curiosity_impulse"]))
        self.rd_dt = max(0.2, min(3.0, self.rd_dt_base + 0.7 * self.control_values["curiosity_impulse"]))

    def _validate_feature_contract(self, *, rd_ok: bool, vol_ok: bool, temporal_ok: bool) -> None:
        if self.rd_enabled and not rd_ok:
            raise GPUUnavailableError(
                "Reaction-diffusion requested (DALI_FISHTANK_RD_ENABLED=1) but GPU RD init failed. "
                "Disable explicitly via DALI_FISHTANK_RD_ENABLED=0."
            )
        if self.vol_enabled and not vol_ok:
            raise GPUUnavailableError(
                "Volumetric rendering requested (DALI_FISHTANK_VOL_ENABLED=1) but volumetric init failed. "
                "Disable explicitly via DALI_FISHTANK_VOL_ENABLED=0."
            )
        if self.temporal_enabled and not temporal_ok:
            raise GPUUnavailableError(
                "Temporal accumulation requested (DALI_FISHTANK_TEMPORAL_ENABLED=1) but temporal init failed. "
                "Disable explicitly via DALI_FISHTANK_TEMPORAL_ENABLED=0."
            )

    def _build_fullscreen_quad(self) -> None:
        vertices = np.array(
            [
                -1.0,
                -1.0,
                1.0,
                -1.0,
                -1.0,
                1.0,
                1.0,
                1.0,
            ],
            dtype="f4",
        )
        self._quad_vbo = self._ctx.buffer(vertices.tobytes())

    def _fullscreen_program(self, fragment_source: str, *, stage: str):
        program = self._ctx.program(
            vertex_shader="""
                #version 430
                in vec2 in_pos;
                out vec2 uv;
                void main() {
                    uv = in_pos * 0.5 + 0.5;
                    gl_Position = vec4(in_pos, 0.0, 1.0);
                }
            """,
            fragment_shader=fragment_source,
        )
        vao = self._ctx.vertex_array(program, [(self._quad_vbo, "2f", "in_pos")])
        if self._quad is None:
            self._quad = vao
        self.log.log("shader_stage_ready", stage=stage)
        return program, vao

    def _init_rd_pipeline(self) -> bool:
        if not self.rd_enabled:
            return False
        try:
            self._rd_tex_a = self._ctx.texture((self.rd_res, self.rd_res), 2, dtype="f4")
            self._rd_tex_b = self._ctx.texture((self.rd_res, self.rd_res), 2, dtype="f4")
            for tex in (self._rd_tex_a, self._rd_tex_b):
                tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
                tex.repeat_x = True
                tex.repeat_y = True
            uv = np.zeros((self.rd_res, self.rd_res, 2), dtype="f4")
            uv[:, :, 0] = 1.0
            mid = self.rd_res // 2
            span = max(8, self.rd_res // 18)
            uv[mid - span : mid + span, mid - span : mid + span, 1] = 1.0
            self._rd_tex_a.write(uv.tobytes())
            self._rd_tex_b.write(uv.tobytes())
            self._rd_fbo_a = self._ctx.framebuffer(color_attachments=[self._rd_tex_a])
            self._rd_fbo_b = self._ctx.framebuffer(color_attachments=[self._rd_tex_b])
            self._rd_prog, self._quad = self._fullscreen_program(
                """
                #version 430
                in vec2 uv;
                out vec4 fragColor;
                uniform sampler2D prev_rd;
                uniform vec2 texel;
                uniform float du;
                uniform float dv;
                uniform float feed;
                uniform float kill;
                uniform float dt;
                uniform vec2 inject_center;
                uniform float inject_strength;
                uniform float inject_radius;
                void main() {
                    vec2 p = uv;
                    vec2 c = texture(prev_rd, p).xy;
                    float u = c.x;
                    float v = c.y;
                    float uL = texture(prev_rd, p + vec2(-texel.x, 0.0)).x;
                    float uR = texture(prev_rd, p + vec2( texel.x, 0.0)).x;
                    float uD = texture(prev_rd, p + vec2(0.0, -texel.y)).x;
                    float uU = texture(prev_rd, p + vec2(0.0,  texel.y)).x;
                    float vL = texture(prev_rd, p + vec2(-texel.x, 0.0)).y;
                    float vR = texture(prev_rd, p + vec2( texel.x, 0.0)).y;
                    float vD = texture(prev_rd, p + vec2(0.0, -texel.y)).y;
                    float vU = texture(prev_rd, p + vec2(0.0,  texel.y)).y;
                    float lapU = (uL + uR + uD + uU - 4.0 * u);
                    float lapV = (vL + vR + vD + vU - 4.0 * v);
                    float uvv = u * v * v;
                    float du_dt = du * lapU - uvv + feed * (1.0 - u);
                    float dv_dt = dv * lapV + uvv - (feed + kill) * v;
                    float dist = distance(p, inject_center);
                    float inject = inject_strength * smoothstep(inject_radius, 0.0, dist);
                    float newU = clamp(u + du_dt * dt - inject * 0.6, 0.0, 1.0);
                    float newV = clamp(v + dv_dt * dt + inject, 0.0, 1.0);
                    fragColor = vec4(newU, newV, 0.0, 1.0);
                }
                """,
                stage="rd_step",
            )
            self.log.log("RD init OK", enabled=True, rd_res=self.rd_res, rd_hz=self.rd_hz)
            return True
        except Exception as exc:
            self._append_shader_error("rd_pipeline", "rd_step", exc)
            self.log.log("RD init FAIL", error=str(exc))
            return False

    def _init_post_pipeline(self) -> tuple[bool, bool]:
        vol_ok = True
        temporal_ok = True
        try:
            self._vol_prog, _ = self._fullscreen_program(
                """
                #version 430
                in vec2 uv;
                out vec4 fragColor;
                uniform sampler2D rd_field;
                uniform float t;
                uniform float density_boost;
                uniform float nebula;
                uniform float curiosity;
                uniform int steps;
                uniform float audio_amp;
                float hash12(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
                float noise3(vec3 p) {
                    vec3 i = floor(p);
                    vec3 f = fract(p);
                    f = f * f * (3.0 - 2.0 * f);
                    float n = dot(i, vec3(1.0, 57.0, 113.0));
                    return mix(
                        mix(mix(hash12(vec2(n + 0.0, n + 1.0)), hash12(vec2(n + 57.0, n + 58.0)), f.x),
                            mix(hash12(vec2(n + 113.0, n + 114.0)), hash12(vec2(n + 170.0, n + 171.0)), f.x), f.y),
                        mix(mix(hash12(vec2(n + 1.0, n + 2.0)), hash12(vec2(n + 58.0, n + 59.0)), f.x),
                            mix(hash12(vec2(n + 114.0, n + 115.0)), hash12(vec2(n + 171.0, n + 172.0)), f.x), f.y), f.z
                    );
                }
                void main() {
                    vec2 p = uv;
                    vec2 rdgrad = vec2(
                        texture(rd_field, p + vec2(0.001, 0.0)).y - texture(rd_field, p - vec2(0.001, 0.0)).y,
                        texture(rd_field, p + vec2(0.0, 0.001)).y - texture(rd_field, p - vec2(0.0, 0.001)).y
                    );
                    vec3 ro = vec3((p - 0.5) * vec2(1.7, 1.0), -2.0);
                    vec3 rd = normalize(vec3((p - 0.5) * vec2(1.7, 1.0), 1.2));
                    float jitter = hash12(p + t) - 0.5;
                    float stepSz = 2.5 / float(max(12, steps));
                    vec3 col = vec3(0.0);
                    float alpha = 0.0;
                    for (int i = 0; i < 192; i++) {
                        if (i >= steps) break;
                        float s = (float(i) + jitter) * stepSz;
                        vec3 pos = ro + rd * s;
                        vec2 wp = fract(pos.xy * 0.15 + rdgrad * 1.8 + 0.5);
                        float rdm = texture(rd_field, wp).y;
                        float d = noise3(pos * (0.7 + nebula) + vec3(rdgrad * 2.5, t * 0.05));
                        d = max(0.0, d * (0.8 + rdm * 1.5) * density_boost - 0.42);
                        d *= (0.8 + curiosity * 0.6 + audio_amp * 0.3);
                        vec3 c = mix(vec3(0.06, 0.08, 0.17), vec3(1.0, 0.70, 0.38), clamp(d + rdm * 0.6, 0.0, 1.0));
                        float a = clamp(d * 0.18, 0.0, 0.22);
                        col += (1.0 - alpha) * c * a;
                        alpha += (1.0 - alpha) * a;
                        if (alpha > 0.98) break;
                    }
                    fragColor = vec4(col, clamp(alpha, 0.0, 1.0));
                }
                """,
                stage="volumetric",
            )
            self._temporal_prog, _ = self._fullscreen_program(
                """
                #version 430
                in vec2 uv;
                out vec4 fragColor;
                uniform sampler2D curr_tex;
                uniform sampler2D prev_tex;
                uniform float alpha_mix;
                void main() {
                    vec4 curr = texture(curr_tex, uv);
                    vec4 prev = texture(prev_tex, uv);
                    fragColor = mix(curr, prev, alpha_mix);
                }
                """,
                stage="temporal",
            )
            self._copy_prog, _ = self._fullscreen_program(
                """
                #version 430
                in vec2 uv;
                out vec4 fragColor;
                uniform sampler2D src_tex;
                void main() { fragColor = texture(src_tex, uv); }
                """,
                stage="copy",
            )
            self._bloom_extract_prog, _ = self._fullscreen_program(
                """
                #version 430
                in vec2 uv;
                out vec4 fragColor;
                uniform sampler2D src_tex;
                void main() {
                    vec3 c = texture(src_tex, uv).rgb;
                    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
                    vec3 b = max(c - vec3(0.32), vec3(0.0)) * (0.6 + l * 0.7);
                    fragColor = vec4(b, 1.0);
                }
                """,
                stage="bloom_extract",
            )
            self._blur_prog, _ = self._fullscreen_program(
                """
                #version 430
                in vec2 uv;
                out vec4 fragColor;
                uniform sampler2D src_tex;
                uniform vec2 axis;
                void main() {
                    vec3 sum = vec3(0.0);
                    vec2 o = axis;
                    sum += texture(src_tex, uv - 4.0 * o).rgb * 0.05;
                    sum += texture(src_tex, uv - 2.0 * o).rgb * 0.12;
                    sum += texture(src_tex, uv).rgb * 0.26;
                    sum += texture(src_tex, uv + 2.0 * o).rgb * 0.12;
                    sum += texture(src_tex, uv + 4.0 * o).rgb * 0.05;
                    fragColor = vec4(sum, 1.0);
                }
                """,
                stage="bloom_blur",
            )
            self._tonemap_prog, _ = self._fullscreen_program(
                """
                #version 430
                in vec2 uv;
                out vec4 fragColor;
                uniform sampler2D hdr_tex;
                uniform sampler2D bloom_tex;
                uniform float bloom_strength;
                uniform float exposure;
                uniform int tonemap_mode;
                vec3 aces(vec3 x) {
                    const float a = 2.51;
                    const float b = 0.03;
                    const float c = 2.43;
                    const float d = 0.59;
                    const float e = 0.14;
                    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
                }
                void main() {
                    vec3 hdr = texture(hdr_tex, uv).rgb;
                    vec3 bloom = texture(bloom_tex, uv).rgb * bloom_strength;
                    vec3 color = hdr + bloom;
                    color = vec3(1.0) - exp(-color * exposure);
                    if (tonemap_mode == 1) {
                        color = aces(color);
                    } else {
                        color = color / (color + vec3(1.0));
                    }
                    color = pow(max(color, vec3(0.0)), vec3(1.0 / 2.2));
                    fragColor = vec4(color, 1.0);
                }
                """,
                stage="tonemap",
            )
            self.log.log("VOL init OK", enabled=self.vol_enabled, steps=self.vol_steps)
            self.log.log("ACES OK", tonemap=self.tonemap_mode)
            self.log.log("BLOOM OK", enabled=self.bloom_enabled, strength=self.bloom_strength)
        except Exception as exc:
            self._append_shader_error("post_pipeline", "vol/temporal/post", exc)
            vol_ok = False if self.vol_enabled else True
            temporal_ok = False if self.temporal_enabled else True
            self.log.log("VOL init FAIL", error=str(exc))
        return vol_ok, temporal_ok

    def _ensure_post_buffers(self) -> None:
        if self.fb_w <= 0 or self.fb_h <= 0:
            raise GPUUnavailableError("framebuffer not ready for post pipeline")
        if self._post_w == self.fb_w and self._post_h == self.fb_h and self._scene_tex is not None:
            return
        self._post_w = int(self.fb_w)
        self._post_h = int(self.fb_h)
        self._scene_tex = self._ctx.texture((self._post_w, self._post_h), 4, dtype="f2")
        self._scene_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._scene_fbo = self._ctx.framebuffer(color_attachments=[self._scene_tex])
        self._temporal_tex_a = self._ctx.texture((self._post_w, self._post_h), 4, dtype="f2")
        self._temporal_tex_b = self._ctx.texture((self._post_w, self._post_h), 4, dtype="f2")
        self._temporal_tex_a.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._temporal_tex_b.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._temporal_fbo_a = self._ctx.framebuffer(color_attachments=[self._temporal_tex_a])
        self._temporal_fbo_b = self._ctx.framebuffer(color_attachments=[self._temporal_tex_b])
        half_w = max(64, self._post_w // 2)
        half_h = max(64, self._post_h // 2)
        self._bloom_tex_a = self._ctx.texture((half_w, half_h), 4, dtype="f2")
        self._bloom_tex_b = self._ctx.texture((half_w, half_h), 4, dtype="f2")
        self._bloom_tex_a.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._bloom_tex_b.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._bloom_fbo_a = self._ctx.framebuffer(color_attachments=[self._bloom_tex_a])
        self._bloom_fbo_b = self._ctx.framebuffer(color_attachments=[self._bloom_tex_b])

    def _rd_prev_tex(self):
        return self._rd_tex_a if self._rd_ping == 0 else self._rd_tex_b

    def _rd_next_fbo(self):
        return self._rd_fbo_b if self._rd_ping == 0 else self._rd_fbo_a

    def _step_rd_field(self, now: float) -> None:
        if not self.rd_enabled or self._rd_prog is None:
            return
        step = 1.0 / self.rd_hz
        steps = 0
        while now - self._last_rd_step_ts >= step and steps < 4:
            inject_t = max(0.0, self._rd_inject_until - now)
            inject_strength = max(0.0, min(1.6, inject_t * 0.8 + self.control_values["curiosity_impulse"] * 0.6))
            if inject_strength > 0.01:
                seed = self._rd_inject_seed or now
                x = 0.5 + 0.22 * math.sin(seed * 1.7)
                y = 0.5 + 0.22 * math.cos(seed * 1.3)
            else:
                x = 0.5 + 0.15 * math.sin(now * 0.23)
                y = 0.5 + 0.15 * math.cos(now * 0.19)
            prev_tex = self._rd_prev_tex()
            next_fbo = self._rd_next_fbo()
            next_fbo.use()
            self._ctx.disable(moderngl.BLEND)
            prev_tex.use(location=0)
            self._rd_prog["prev_rd"].value = 0
            self._rd_prog["texel"].value = (1.0 / self.rd_res, 1.0 / self.rd_res)
            self._rd_prog["du"].value = self.rd_du
            self._rd_prog["dv"].value = self.rd_dv
            self._rd_prog["feed"].value = self.rd_feed
            self._rd_prog["kill"].value = self.rd_kill
            self._rd_prog["dt"].value = self.rd_dt
            self._rd_prog["inject_center"].value = (x, y)
            self._rd_prog["inject_strength"].value = inject_strength
            self._rd_prog["inject_radius"].value = 0.16 + 0.05 * self.control_values["symmetry_bias"]
            self._quad.render(mode=moderngl.TRIANGLE_STRIP)
            self._rd_ping = 1 - self._rd_ping
            self._last_rd_step_ts += step
            steps += 1

    def _rd_active_tex(self):
        if self.rd_enabled:
            return self._rd_prev_tex()
        return self._rd_dummy_tex

    def _init_gpu_backend(self) -> None:
        if moderngl is None or np is None:
            if self.require_gpu:
                raise GPUUnavailableError("moderngl/numpy unavailable")
            return
        try:
            if self.headless:
                self._ctx = moderngl.create_standalone_context(require=430, backend="egl")
                self._window = None
                self.backend = "egl-headless"
            else:
                if glfw is None:
                    raise GPUUnavailableError("glfw unavailable for non-headless mode")
                if not glfw.init():
                    raise GPUUnavailableError("glfw init failed")
                glfw.window_hint(glfw.VISIBLE, glfw.TRUE)
                glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
                glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
                fullscreen = os.environ.get("DALI_FISHTANK_FULLSCREEN", "1") == "1"
                monitor = glfw.get_primary_monitor() if fullscreen else None
                width = self.width
                height = self.height
                if monitor is not None:
                    try:
                        mode = glfw.get_video_mode(monitor)
                        if mode is not None:
                            width = int(mode.size.width)
                            height = int(mode.size.height)
                    except Exception:
                        pass
                window = glfw.create_window(width, height, "DALI FishTankRenderer", monitor, None)
                if window is None:
                    glfw.terminate()
                    raise GPUUnavailableError("glfw window creation failed")
                glfw.make_context_current(window)
                swap_interval = int(os.environ.get("DALI_FISHTANK_SWAP_INTERVAL", "1") or 1)
                glfw.swap_interval(swap_interval)
                self._window = window
                self._ctx = moderngl.create_context(require=430)
                self.backend = "glfw-fullscreen" if fullscreen else "glfw-windowed"
                self.log.log("glfw_window_ready", width=width, height=height, fullscreen=fullscreen, swap_interval=swap_interval)

            ctx = self._ctx
            self._present_first_frame_sentinel()
            self._build_fullscreen_quad()
            self._rd_dummy_tex = ctx.texture((1, 1), 2, dtype="f4", data=np.array([1.0, 0.0], dtype="f4").tobytes())
            self._rd_dummy_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
            try:
                self._prog = ctx.program(
                    vertex_shader="""
                        #version 430
                        in vec2 in_pos;
                        uniform float point_size;
                        void main() {
                            gl_Position = vec4(in_pos, 0.0, 1.0);
                            gl_PointSize = point_size;
                        }
                    """,
                    fragment_shader="""
                        #version 430
                        out vec4 fragColor;
                        uniform float warmth;
                        uniform float luminosity;
                        uniform float exposure;
                        uniform float contrast;
                        uniform float saturation;
                        uniform float bloom;
                        void main() {
                            vec2 uv = gl_PointCoord * 2.0 - 1.0;
                            float r = dot(uv, uv);
                            float alpha = smoothstep(1.0, 0.2, r) * luminosity;
                            vec3 cold = vec3(0.08, 0.15, 0.34);
                            vec3 hot = vec3(1.0, 0.72, 0.32);
                            vec3 color = mix(cold, hot, warmth);
                            color *= (0.4 + luminosity * 1.8);
                            color = vec3(1.0) - exp(-color * exposure);
                            float luma = dot(color, vec3(0.2126, 0.7152, 0.0722));
                            color = mix(vec3(luma), color, saturation);
                            color = (color - 0.5) * contrast + 0.5;
                            color += bloom * alpha;
                            fragColor = vec4(clamp(color, 0.0, 2.5), clamp(alpha * (0.6 + bloom * 0.18), 0.0, 1.0));
                        }
                    """,
                )
            except Exception as exc:
                self._append_shader_error("render_program", "vertex+fragment", exc)
                raise GPUUnavailableError(f"render shader compile/link failed: {exc}") from exc
            try:
                self._compute = ctx.compute_shader(
                    """
                    #version 430
                    layout(local_size_x=256) in;
                    layout(std430, binding=0) buffer Pos { vec2 pos[]; };
                    layout(std430, binding=1) buffer Vel { vec2 vel[]; };
                    layout(binding=2) uniform sampler2D rd_field;
                    uniform vec2 rd_texel;
                    uniform float rd_coupling;
                    uniform float dt;
                    uniform float turbulence;
                    uniform float velocity_scale;
                    uniform float vortex;
                    uniform uint n;
                    void main() {
                        uint i = gl_GlobalInvocationID.x;
                        if (i >= n) { return; }
                        vec2 p = pos[i];
                        vec2 v = vel[i];
                        vec2 swirl = vec2(-p.y, p.x) * (0.4 + vortex);
                        vec2 uv = clamp(p * 0.5 + 0.5, vec2(0.001), vec2(0.999));
                        float l = texture(rd_field, uv - vec2(rd_texel.x, 0.0)).y;
                        float r = texture(rd_field, uv + vec2(rd_texel.x, 0.0)).y;
                        float d = texture(rd_field, uv - vec2(0.0, rd_texel.y)).y;
                        float u = texture(rd_field, uv + vec2(0.0, rd_texel.y)).y;
                        vec2 rd_grad = vec2(r - l, u - d);
                        v += swirl * dt * 0.35;
                        v += rd_grad * rd_coupling * dt * 1.8;
                        float noise = sin(float(i) * 0.017 + dt * 17.0) * turbulence;
                        v += vec2(noise, -noise) * dt * 0.25;
                        v *= (0.985 - turbulence * 0.02);
                        p += v * dt * (0.5 + velocity_scale * 1.5);
                        if (length(p) > 1.2) {
                            p = normalize(p) * -1.0;
                        }
                        pos[i] = p;
                        vel[i] = v;
                    }
                    """
                )
            except Exception as exc:
                self._append_shader_error("compute_program", "compute", exc)
                raise GPUUnavailableError(f"compute shader compile/link failed: {exc}") from exc

            self._ssbo_pos = ctx.buffer(self.positions.tobytes())
            self._ssbo_vel = ctx.buffer(self.velocities.tobytes())
            self._ssbo_pos.bind_to_storage_buffer(0)
            self._ssbo_vel.bind_to_storage_buffer(1)
            self._vao = ctx.vertex_array(self._prog, [(self._ssbo_pos, "2f", "in_pos")])
            rd_ok = self._init_rd_pipeline()
            vol_ok, temporal_ok = self._init_post_pipeline()
            self._validate_feature_contract(rd_ok=rd_ok or (not self.rd_enabled), vol_ok=vol_ok, temporal_ok=temporal_ok)
            self.gpu_mode = True
        except Exception as exc:
            self.log.log("gpu_init_failed", error=str(exc))
            self.gpu_mode = False
            if self.require_gpu:
                raise GPUUnavailableError(str(exc))

    def set_inference_active(self, active: bool) -> None:
        self.inference_active = bool(active)

    def update_signals(self, telemetry: dict[str, Any], tacti: dict[str, Any]) -> None:
        fan_speed = telemetry.get("fan_gpu") if telemetry.get("fan_gpu") is not None else telemetry.get("fan_cpu")
        self.signals = RendererSignals(
            arousal=float(tacti.get("arousal", 0.5) or 0.5),
            gpu_util=float(telemetry.get("gpu_util", 0.0) or 0.0),
            gpu_vram=float(telemetry.get("gpu_vram", 0.0) or 0.0),
            gpu_vram_used_mb=float(telemetry.get("gpu_vram_used_mb", 0.0) or 0.0),
            cpu_temp=float(telemetry.get("cpu_temp", 50.0) or 50.0),
            fan_speed=float(fan_speed or 1200.0),
            disk_io=float(telemetry.get("disk_io", 0.0) or 0.0),
            memory_density=float(tacti.get("memory_recall_density", 0.0) or 0.0),
        )
        # Visual mapping layer.
        self.shader_params["luminosity"] = clamp01(0.25 + self.signals.arousal * 0.75)
        self.shader_params["turbulence"] = clamp01(0.15 + self.signals.arousal * 0.65)
        self.shader_params["velocity"] = clamp01(0.1 + self.signals.gpu_util * 0.9)
        self.shader_params["nebula"] = clamp01(0.2 + self.signals.gpu_vram * 0.8)
        self.shader_params["warmth"] = clamp01((self.signals.cpu_temp - 30.0) / 60.0)
        self.shader_params["vortex"] = clamp01((self.signals.fan_speed - 600.0) / 2200.0)
        self.shader_params["ripple"] = clamp01(self.signals.disk_io)
        self.shader_params["cloud"] = clamp01(self.signals.memory_density)

    def inject_curiosity_event(self, curiosity_event: dict[str, Any]) -> None:
        now = time.monotonic()
        self.curiosity_impulses.append(
            {
                "ts": now,
                "seed": curiosity_event.get("seed"),
                "leads": curiosity_event.get("leads", []),
            }
        )
        self.curiosity_impulses = self.curiosity_impulses[-8:]
        self._rd_inject_until = max(self._rd_inject_until, now + 1.8)
        self._rd_inject_seed = float(abs(hash(str(curiosity_event.get("seed") or now))) % 10000) / 10000.0

    def _cpu_step(self, dt: float) -> None:
        if np is None:
            for i in range(self.agent_count):
                px, py = self.positions[i]
                vx, vy = self.velocities[i]
                swirl_x, swirl_y = -py, px
                jitter = (random.random() - 0.5) * self.shader_params["turbulence"]
                vx = (vx + swirl_x * 0.002 + jitter) * 0.992
                vy = (vy + swirl_y * 0.002 - jitter) * 0.992
                px += vx * dt * (0.5 + self.shader_params["velocity"])
                py += vy * dt * (0.5 + self.shader_params["velocity"])
                if px > 1.2 or px < -1.2:
                    px = -px * 0.7
                if py > 1.2 or py < -1.2:
                    py = -py * 0.7
                self.positions[i] = [px, py]
                self.velocities[i] = [vx, vy]
            return

        pos = self.positions
        vel = self.velocities

        center = pos.mean(axis=0, keepdims=True)
        to_center = center - pos
        dist = np.linalg.norm(pos, axis=1, keepdims=True) + 1e-6
        radial = -pos / dist
        swirl = np.concatenate((-pos[:, 1:2], pos[:, 0:1]), axis=1)

        flock_gain = 0.03 + (self.shader_params["cloud"] * 0.08)
        repel_gain = 0.02 + (self.shader_params["ripple"] * 0.07)
        vortex_gain = 0.04 + (self.shader_params["vortex"] * 0.12)
        diffuse_gain = 0.006 + (self.shader_params["turbulence"] * 0.04)

        # Emergent blend: flock + repel + cluster + merge + diffuse.
        vel += to_center * flock_gain * dt
        vel += radial * repel_gain * dt
        vel += swirl * vortex_gain * dt
        vel += np.random.normal(0.0, diffuse_gain, size=vel.shape).astype("float32")

        if self.curiosity_impulses:
            newest = self.curiosity_impulses[-1]
            age = time.monotonic() - float(newest.get("ts", 0.0))
            if age < 12.0:
                seed = str(newest.get("seed") or "0")
                pulse = (int(seed[:6], 16) % 1000) / 1000.0
                branch_dir = np.array([[math.cos(pulse * math.tau), math.sin(pulse * math.tau)]], dtype="float32")
                vel += branch_dir * (0.04 * (1.0 - age / 12.0))

        damping = 0.988 - (0.02 if self.inference_active else 0.0)
        vel *= max(0.90, damping)

        speed_scale = 0.35 + self.shader_params["velocity"] * 1.8
        if self.inference_active:
            speed_scale *= 0.55
        pos += vel * dt * speed_scale

        wrapped = np.linalg.norm(pos, axis=1) > 1.25
        if np.any(wrapped):
            pos[wrapped] *= -0.78
            vel[wrapped] *= 0.5

    def _gpu_step(self, dt: float) -> None:
        if not self.gpu_mode:
            if self.require_gpu:
                raise GPUUnavailableError("GPU mode disabled")
            self._cpu_step(dt)
            return
        try:
            rd_tex = self._rd_active_tex()
            if rd_tex is not None:
                rd_tex.use(location=2)
                self._compute["rd_field"].value = 2
                tex_scale = float(self.rd_res) if self.rd_enabled else 1.0
                self._compute["rd_texel"].value = (1.0 / tex_scale, 1.0 / tex_scale)
            self._compute["rd_coupling"].value = max(
                0.0,
                min(
                    2.5,
                    0.35
                    + (self.control_values.get("curiosity_impulse", 0.0) * 1.0)
                    + (self.control_values.get("turbulence_boost", 0.0) * 0.35)
                    + (self.shader_params.get("cloud", 0.0) * 0.5),
                ),
            )
            self._compute["dt"].value = float(max(1e-4, dt))
            self._compute["turbulence"].value = float(self.shader_params["turbulence"])
            self._compute["velocity_scale"].value = float(self.shader_params["velocity"])
            self._compute["vortex"].value = float(self.shader_params["vortex"])
            self._compute["n"].value = int(self.agent_count)
            groups = (self.agent_count + 255) // 256
            self._compute.run(group_x=groups)
        except Exception as exc:
            self.log.log("gpu_step_failed", error=str(exc))
            self.gpu_mode = False
            if self.require_gpu:
                raise GPUUnavailableError(str(exc))
            self._cpu_step(dt)

    def update_state(self) -> None:
        now = time.monotonic()
        dt = max(1e-3, min(0.2, now - self.last_frame_ts))
        self.last_frame_ts = now
        self.last_frame_ms = dt * 1000.0
        instant_fps = 1.0 / dt
        self.renderer_fps = instant_fps if self.renderer_fps <= 0.0 else (self.renderer_fps * 0.92 + instant_fps * 0.08)
        self._refresh_control_values()
        self._gpu_step(dt)
        self.frame_index += 1

    def _render_volume_to_scene(self, now: float) -> None:
        if self._scene_fbo is None:
            return
        self._scene_fbo.use()
        self._ctx.disable(moderngl.BLEND)
        clear_r = min(0.18, 0.03 + (self.effective_exposure * 0.01))
        clear_g = min(0.2, 0.04 + (self.effective_exposure * 0.012))
        clear_b = min(0.28, 0.08 + (self.effective_exposure * 0.02))
        self._ctx.clear(clear_r, clear_g, clear_b, 1.0)
        if self.vol_enabled and self._vol_prog is not None and self._quad is not None:
            rd_tex = self._rd_active_tex()
            if rd_tex is not None:
                rd_tex.use(location=3)
            audio_amp = clamp01(safe_float(os.environ.get("OPENCLAW_AUDIO_SIM", 0.0), 0.0))
            self._vol_prog["rd_field"].value = 3
            self._vol_prog["t"].value = float(now)
            self._vol_prog["density_boost"].value = max(0.2, min(3.0, self.control_values["density_boost"]))
            self._vol_prog["nebula"].value = float(self.shader_params["nebula"])
            self._vol_prog["curiosity"].value = float(self.control_values["curiosity_impulse"])
            self._vol_prog["steps"].value = int(self.vol_steps)
            self._vol_prog["audio_amp"].value = audio_amp
            self._quad.render(mode=moderngl.TRIANGLE_STRIP)
            target = 0.12 + self.shader_params["nebula"] * 0.45 + self.control_values["density_boost"] * 0.08
            self.vol_luminance_mean = (self.vol_luminance_mean * 0.82) + (target * 0.18)

    def _render_particles_to_scene(self, now: float) -> None:
        if self._scene_fbo is None:
            return
        self._scene_fbo.use()
        curiosity_pulse = max(0.0, self._curiosity_pulse_until - now)
        self._ctx.enable(moderngl.BLEND)
        self._ctx.blend_func = moderngl.ONE, moderngl.ONE
        self._prog["point_size"].value = (
            1.7
            + (self.shader_params["nebula"] * 2.4)
            + max(0.0, self.control_values["density_boost"] - 1.0) * 2.4
            + (curiosity_pulse * 2.6)
        )
        self._prog["warmth"].value = self.shader_params["warmth"]
        self._prog["luminosity"].value = self.shader_params["luminosity"]
        self._prog["exposure"].value = self.effective_exposure
        self._prog["contrast"].value = self.effective_contrast
        self._prog["saturation"].value = self.effective_saturation
        self._prog["bloom"].value = self.effective_bloom
        self._vao.render(mode=moderngl.POINTS, vertices=self.particles_visible)
        self._ctx.disable(moderngl.BLEND)

    def _post_to_screen(self) -> None:
        if self._scene_tex is None or self._quad is None:
            return
        source_tex = self._scene_tex
        if self.temporal_enabled and self._temporal_prog is not None and self._temporal_fbo_b is not None:
            prev_tex = self._temporal_tex_a if self._temporal_ping == 0 else self._temporal_tex_b
            out_fbo = self._temporal_fbo_b if self._temporal_ping == 0 else self._temporal_fbo_a
            out_tex = self._temporal_tex_b if self._temporal_ping == 0 else self._temporal_tex_a
            out_fbo.use()
            self._ctx.disable(moderngl.BLEND)
            self._scene_tex.use(location=0)
            prev_tex.use(location=1)
            self._temporal_prog["curr_tex"].value = 0
            self._temporal_prog["prev_tex"].value = 1
            alpha = self.temporal_alpha
            if self.control_values.get("curiosity_impulse", 0.0) > 0.5:
                alpha = max(0.75, alpha - 0.12)
            self._temporal_prog["alpha_mix"].value = float(alpha)
            self._quad.render(mode=moderngl.TRIANGLE_STRIP)
            self._temporal_ping = 1 - self._temporal_ping
            source_tex = out_tex

        bloom_tex = source_tex
        if self.bloom_enabled and self._bloom_extract_prog is not None and self._bloom_fbo_a is not None:
            self._bloom_fbo_a.use()
            source_tex.use(location=0)
            self._bloom_extract_prog["src_tex"].value = 0
            self._quad.render(mode=moderngl.TRIANGLE_STRIP)

            self._bloom_fbo_b.use()
            self._bloom_tex_a.use(location=0)
            self._blur_prog["src_tex"].value = 0
            self._blur_prog["axis"].value = (1.0 / max(1, self._bloom_tex_a.size[0]), 0.0)
            self._quad.render(mode=moderngl.TRIANGLE_STRIP)

            self._bloom_fbo_a.use()
            self._bloom_tex_b.use(location=0)
            self._blur_prog["src_tex"].value = 0
            self._blur_prog["axis"].value = (0.0, 1.0 / max(1, self._bloom_tex_b.size[1]))
            self._quad.render(mode=moderngl.TRIANGLE_STRIP)
            bloom_tex = self._bloom_tex_a

        self._ctx.screen.use()
        self._ctx.viewport = (0, 0, self.fb_w, self.fb_h)
        self._ctx.disable(moderngl.BLEND)
        source_tex.use(location=0)
        bloom_tex.use(location=1)
        self._tonemap_prog["hdr_tex"].value = 0
        self._tonemap_prog["bloom_tex"].value = 1
        self._tonemap_prog["bloom_strength"].value = float(self.effective_bloom if self.bloom_enabled else 0.0)
        self._tonemap_prog["exposure"].value = float(self.effective_exposure)
        self._tonemap_prog["tonemap_mode"].value = 1 if self.tonemap_mode == "aces" else 0
        self._quad.render(mode=moderngl.TRIANGLE_STRIP)

    def render_scene(self) -> None:
        if not self.gpu_mode:
            return
        try:
            if self._window is None or glfw is None:
                return
            glfw.make_context_current(self._window)
            glfw.poll_events()
            if glfw.window_should_close(self._window):
                if self.require_gpu:
                    raise GPUUnavailableError("render window closed")
                return
            self._ensure_nonzero_framebuffer()
            self._ensure_post_buffers()
            now = time.monotonic()
            self._step_rd_field(now)
            self._render_volume_to_scene(now)
            self._render_particles_to_scene(now)
            self._post_to_screen()
            glfw.swap_buffers(self._window)
            self._check_gl_error()
        except Exception as exc:
            self.log.log("render_failed", error=str(exc))
            self.gpu_mode = False
            if self.require_gpu:
                raise GPUUnavailableError(str(exc))

    def draw_overlay(self) -> None:
        # Headless runtime does not use a separate overlay pass.
        return

    def dream_cycle(self) -> dict[str, Any]:
        ts = utc_now_iso()
        rng = random.Random(int(time.time()) // 7)
        mutation = max(0.2, min(2.0, float(self.control_values.get("mutation_rate", 1.0))))
        self.shader_params["turbulence"] = clamp01(
            self.shader_params["turbulence"] + rng.uniform(-0.12 * mutation, 0.12 * mutation)
        )
        self.shader_params["vortex"] = clamp01(self.shader_params["vortex"] + rng.uniform(-0.10 * mutation, 0.10 * mutation))
        self.shader_params["nebula"] = clamp01(self.shader_params["nebula"] + rng.uniform(-0.08 * mutation, 0.08 * mutation))
        self.shader_params["cloud"] = clamp01(self.shader_params["cloud"] + rng.uniform(-0.07 * mutation, 0.07 * mutation))
        payload = {
            "ts": ts,
            "mode": "dream_cycle",
            "shader_parameters": dict(self.shader_params),
            "frame": self.frame_index,
            "curiosity_branches": len(self.curiosity_impulses),
        }
        atomic_write_json(DREAM_STATES_DIR / f"{ts.replace(':', '').replace('-', '')}.json", payload)
        self.log.log("dream_cycle", frame=self.frame_index)
        return payload

    def capture_state(self) -> dict[str, Any]:
        if np is None:
            sample = self.positions[:128]
        else:
            sample = self.positions[:512].tolist()
        return {
            "ts": utc_now_iso(),
            "active_renderer_name": self.active_renderer_name,
            "active_renderer_version": self.active_renderer_version,
            "active_renderer_id": self.active_renderer_id,
            "particle_state": {
                "count": self.agent_count,
                "sample": sample,
            },
            "shader_parameters": dict(self.shader_params),
            "camera": {
                "x": 0.0,
                "y": 0.0,
                "z": 1.0,
                "yaw": 0.0,
                "pitch": 0.0,
            },
            "gpu_mode": self.gpu_mode,
            "backend": self.backend,
            "renderer_fps": round(float(self.renderer_fps), 3),
            "fps": round(float(self.renderer_fps), 3),
            "particle_count": self.agent_count,
            "particles_target": int(self.particles_target),
            "particles_visible": int(self.particles_visible),
            "vram_mb_used": round(float(self.signals.gpu_vram_used_mb), 3),
            "fb_w": int(self.fb_w),
            "fb_h": int(self.fb_h),
            "last_frame_ms": round(float(self.last_frame_ms), 3),
            "exposure_base": round(float(self.exposure_base), 3),
            "exposure_effective": round(float(self.effective_exposure), 3),
            "bloom_strength": round(float(self.effective_bloom), 3),
            "contrast": round(float(self.effective_contrast), 3),
            "saturation": round(float(self.effective_saturation), 3),
            "controls": self.controls_snapshot,
            "inference_active": self.inference_active,
            "curiosity_events": len(self.curiosity_impulses),
            "rd_enabled": bool(self.rd_enabled),
            "vol_enabled": bool(self.vol_enabled),
            "temporal_enabled": bool(self.temporal_enabled),
            "tonemap": self.tonemap_mode,
            "bloom_enabled": bool(self.bloom_enabled),
            "rd_res": int(self.rd_res),
            "rd_hz": float(self.rd_hz),
            "rd_params": {
                "feed": round(float(self.rd_feed), 5),
                "kill": round(float(self.rd_kill), 5),
                "du": round(float(self.rd_du), 5),
                "dv": round(float(self.rd_dv), 5),
                "dt": round(float(self.rd_dt), 5),
            },
            "vol_steps": int(self.vol_steps),
            "temporal_alpha": round(float(self.temporal_alpha), 4),
            "vol_luminance_mean": round(float(self.vol_luminance_mean), 5),
            "motion_scalar": round(float(self._motion_scalar), 5),
        }

    def persist_state(self) -> dict[str, Any]:
        payload = self.capture_state()
        payload["frame"] = self.frame_index
        atomic_write_json(self.output_path, payload)
        return payload

    def tick(self) -> dict[str, Any]:
        self.update_state()
        self.render_scene()
        self.draw_overlay()
        return self.persist_state()

    def close(self) -> None:
        if self._window is not None and glfw is not None:
            try:
                glfw.destroy_window(self._window)
                glfw.terminate()
            except Exception:
                pass
