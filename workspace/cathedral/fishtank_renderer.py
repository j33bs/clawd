from __future__ import annotations

import hashlib
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

try:
    import tkinter as tk
except Exception:  # pragma: no cover - optional dependency
    tk = None


@dataclass
class RendererSignals:
    arousal: float = 0.5
    gpu_temp: float = 0.0
    gpu_util: float = 0.0
    gpu_vram: float = 0.0
    gpu_vram_used_mb: float = 0.0
    cpu_temp: float = 50.0
    fan_speed: float = 1200.0
    disk_io: float = 0.0
    memory_density: float = 0.0


@dataclass
class MirrorState:
    baseline: float = 0.5
    reasoning: float = 0.0
    insight: float = 0.0
    learning: float = 0.0
    attention: float = 0.0
    overload: float = 0.0
    coherence: float = 0.5
    reflection_phase: float = 0.0
    collapse_risk: float = 0.0
    repair_progress: float = 0.0


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
        allow_gpu_backend: bool = True,
        allow_visible_attach: bool = True,
        control_bus: Any | None = None,
        output_path: Path = FISHTANK_STATE_PATH,
    ):
        ensure_runtime_dirs()
        self.output_path = output_path
        self.width = int(width)
        self.height = int(height)
        self.headless = bool(headless)
        self.require_gpu = bool(require_gpu)
        self.allow_gpu_backend = bool(allow_gpu_backend)
        self.allow_visible_attach = bool(allow_visible_attach)
        preset = str(os.environ.get("DALI_FISHTANK_PRESET", "") or "").strip().lower()
        self.active_preset = preset
        self.work_mode_enabled = preset in {"work_mode", "work_mode_consciousness_mirror", "work_mode_consciousness"}
        self.min_agent_count = 2048 if self.work_mode_enabled else 150_000
        self.max_agent_count = 65_536 if self.work_mode_enabled else 1_000_000
        if self.work_mode_enabled:
            env_grid_w = int(safe_float(os.environ.get("DALI_FISHTANK_WORK_GRID_WIDTH", 960), 960))
            env_grid_h = int(safe_float(os.environ.get("DALI_FISHTANK_WORK_GRID_HEIGHT", 540), 540))
            grid_w = max(64, min(2048, env_grid_w))
            grid_h = max(48, min(1152, env_grid_h))
            self._work_grid_shape = (int(grid_h), int(grid_w))
            requested_particles = int(
                safe_float(os.environ.get("DALI_FISHTANK_WORK_PARTICLE_CAP", min(int(agent_count), self.max_agent_count)), min(int(agent_count), self.max_agent_count))
            )
            self.agent_count = max(self.min_agent_count, min(self.max_agent_count, requested_particles))
        else:
            self._work_grid_shape = (0, 0)
            self.agent_count = max(self.min_agent_count, min(self.max_agent_count, int(agent_count)))
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
        self._last_window_close_log_ts = 0.0
        self._visible_attach_blocked_logged = False
        self._software_window = None
        self._software_canvas = None
        self._software_window_closed = False
        self._software_cell_size = 0
        self._software_last_render_ts = 0.0
        self._software_starfield: list[tuple[float, float, float]] = []
        self._work_recent_pulses: list[dict[str, float]] = []
        self._work_growth_target_ticks = max(
            1200,
            int(safe_float(os.environ.get("DALI_FISHTANK_WORK_GROWTH_TICKS", 18000), 18000)),
        )
        self._work_step_interval_s = max(
            0.02,
            safe_float(os.environ.get("DALI_FISHTANK_WORK_STEP_INTERVAL_S", 0.033), 0.033),
        )
        self._work_visual_time_scale = max(
            0.001,
            min(1.0, safe_float(os.environ.get("DALI_FISHTANK_WORK_VISUAL_TIME_SCALE", 1.0), 1.0)),
        )
        self._work_step_accumulator = 0.0
        self._work_seed_clusters = max(
            1,
            min(8, int(safe_float(os.environ.get("DALI_FISHTANK_WORK_SEED_CLUSTERS", 3), 3))),
        )
        self._work_target_alive_ratio = max(
            0.004,
            min(0.12, safe_float(os.environ.get("DALI_FISHTANK_WORK_TARGET_ALIVE_RATIO", 0.038), 0.038)),
        )
        self._work_starfield_density = max(
            0.0,
            min(1.0, safe_float(os.environ.get("DALI_FISHTANK_WORK_STARFIELD_DENSITY", 0.2), 0.2)),
        )
        self._work_background_dots_enabled = _env_truthy("DALI_FISHTANK_WORK_BACKGROUND_DOTS", "1")
        self._work_novelty_pulse_limit = max(
            2,
            min(16, int(safe_float(os.environ.get("DALI_FISHTANK_WORK_PULSE_LIMIT", 10), 10))),
        )
        self._work_core_age_threshold = max(
            1.0,
            safe_float(os.environ.get("DALI_FISHTANK_WORK_CORE_AGE_THRESHOLD", 1.8), 1.8),
        )
        self._work_local_growth_radius = max(
            2,
            min(40, int(safe_float(os.environ.get("DALI_FISHTANK_WORK_LOCAL_GROWTH_RADIUS", 10), 10))),
        )
        self._work_branch_length = max(
            2,
            min(48, int(safe_float(os.environ.get("DALI_FISHTANK_WORK_BRANCH_LENGTH", 9), 9))),
        )
        self._work_branch_persistence = max(
            0.4,
            min(0.995, safe_float(os.environ.get("DALI_FISHTANK_WORK_BRANCH_PERSISTENCE", 0.9), 0.9)),
        )
        self._work_branch_thickness_prob = max(
            0.0,
            min(0.25, safe_float(os.environ.get("DALI_FISHTANK_WORK_BRANCH_THICKNESS_PROB", 0.03), 0.03)),
        )
        self._work_render_nodes = _env_truthy("DALI_FISHTANK_WORK_RENDER_NODES", "0")
        self._work_render_smoothing = max(
            0.01,
            min(0.6, safe_float(os.environ.get("DALI_FISHTANK_WORK_RENDER_SMOOTHING", 0.065), 0.065)),
        )
        self._work_junction_glow = _env_truthy("DALI_FISHTANK_WORK_JUNCTION_GLOW", "1")
        self._work_pulses_enabled = _env_truthy("DALI_FISHTANK_WORK_PULSES_ENABLED", "0")
        self._work_growth_memory = 0.0
        self._work_growth_samples = 0
        self._work_growth_last_gain = 0.0
        self._work_gpu_util_ema = 0.0
        self._work_growth_sample_scale = max(
            0.0001,
            min(0.02, safe_float(os.environ.get("DALI_FISHTANK_WORK_GPU_GROWTH_SAMPLE_SCALE", 0.0045), 0.0045)),
        )
        self._work_growth_memory_cap = max(
            0.002,
            min(0.18, safe_float(os.environ.get("DALI_FISHTANK_WORK_GPU_GROWTH_MEMORY_CAP", 0.045), 0.045)),
        )
        self._work_growth_spike_floor = max(
            0.0,
            min(0.8, safe_float(os.environ.get("DALI_FISHTANK_WORK_GPU_GROWTH_SPIKE_FLOOR", 0.08), 0.08)),
        )
        self._work_novel_branch_rate = max(
            0.0,
            min(0.4, safe_float(os.environ.get("DALI_FISHTANK_WORK_NOVEL_BRANCH_RATE", 0.06), 0.06)),
        )
        self._work_branch_turn_std = max(
            0.02,
            min(1.2, safe_float(os.environ.get("DALI_FISHTANK_WORK_BRANCH_TURN_STD", 0.08), 0.08)),
        )
        work_scene_default = "fantasy_landscape" if self.work_mode_enabled else "cellular_automata"
        self._work_scene = str(os.environ.get("DALI_FISHTANK_WORK_SCENE", work_scene_default) or work_scene_default).strip().lower()
        if self._work_scene not in {"cellular_automata", "fantasy_landscape", "therapeutic_bilateral"}:
            self._work_scene = work_scene_default
        self._work_scene_time_scale = max(
            0.02,
            min(2.5, safe_float(os.environ.get("DALI_FISHTANK_WORK_SCENE_TIME_SCALE", 0.28), 0.28)),
        )
        self._fantasy_scene_dimensions = (0, 0)
        self._fantasy_scene_started_ts = time.monotonic()
        self._fantasy_scene_state: dict[str, Any] = {}
        self._therapeutic_scene_dimensions = (0, 0)
        self._therapeutic_scene_started_ts = time.monotonic()
        self._therapeutic_scene_state: dict[str, Any] = {}
        self._therapeutic_sweep_seconds = max(
            4.0,
            min(18.0, safe_float(os.environ.get("DALI_FISHTANK_THERAPEUTIC_SWEEP_SECONDS", 7.5), 7.5)),
        )
        self._therapeutic_settle_seconds = max(
            2.0,
            min(20.0, safe_float(os.environ.get("DALI_FISHTANK_THERAPEUTIC_SETTLE_SECONDS", 4.0), 4.0)),
        )
        self._therapeutic_inhale_seconds = max(
            1.0,
            min(12.0, safe_float(os.environ.get("DALI_FISHTANK_THERAPEUTIC_INHALE_SECONDS", 4.0), 4.0)),
        )
        self._therapeutic_hold_seconds = max(
            0.0,
            min(8.0, safe_float(os.environ.get("DALI_FISHTANK_THERAPEUTIC_HOLD_SECONDS", 2.0), 2.0)),
        )
        self._therapeutic_exhale_seconds = max(
            1.0,
            min(16.0, safe_float(os.environ.get("DALI_FISHTANK_THERAPEUTIC_EXHALE_SECONDS", 5.0), 5.0)),
        )
        self._therapeutic_breath_seconds = self._therapeutic_inhale_seconds + self._therapeutic_hold_seconds + self._therapeutic_exhale_seconds
        self._therapeutic_prompt_interval_s = max(
            8.0,
            min(90.0, safe_float(os.environ.get("DALI_FISHTANK_THERAPEUTIC_PROMPT_INTERVAL_S", 24.0), 24.0)),
        )
        self._therapeutic_motion_gain = max(
            0.15,
            min(1.0, safe_float(os.environ.get("DALI_FISHTANK_THERAPEUTIC_MOTION_GAIN", 0.7), 0.7)),
        )
        self._therapeutic_drift_seconds = max(
            45.0,
            min(900.0, safe_float(os.environ.get("DALI_FISHTANK_THERAPEUTIC_DRIFT_SECONDS", 180.0), 180.0)),
        )
        self._therapeutic_drift_ratio = max(
            0.002,
            min(0.03, safe_float(os.environ.get("DALI_FISHTANK_THERAPEUTIC_DRIFT_RATIO", 0.01), 0.01)),
        )
        self._therapeutic_text_timeout_s = max(
            0.0,
            min(900.0, safe_float(os.environ.get("DALI_FISHTANK_THERAPEUTIC_TEXT_TIMEOUT_S", 60.0), 60.0)),
        )
        self._therapeutic_grounding_enabled = _env_truthy("DALI_FISHTANK_THERAPEUTIC_GROUNDING_ENABLED", "1")
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
        palette_mode = str(os.environ.get("DALI_FISHTANK_PALETTE_MODE", "dusk") or "dusk").strip().lower()
        self.palette_mode = palette_mode if palette_mode in {"dusk", "aurora", "roseglass", "ember", "mono"} else "dusk"
        self.hdr_clamp = max(2.0, min(16.0, safe_float(os.environ.get("DALI_FISHTANK_HDR_CLAMP", 10.0), 10.0)))
        self.bloom_threshold = max(
            0.01,
            min(4.0, safe_float(os.environ.get("DALI_FISHTANK_BLOOM_THRESHOLD", 0.32), 0.32)),
        )
        self.bloom_knee = max(0.001, min(2.0, safe_float(os.environ.get("DALI_FISHTANK_BLOOM_KNEE", 0.28), 0.28)))
        self.white_balance = (
            max(
                0.5,
                min(
                    1.8,
                    safe_float(
                        os.environ.get("DALI_FISHTANK_WHITE_BALANCE_R", os.environ.get("DALI_FISHTANK_WB_R", 1.03)),
                        1.03,
                    ),
                ),
            ),
            max(
                0.5,
                min(
                    1.8,
                    safe_float(
                        os.environ.get("DALI_FISHTANK_WHITE_BALANCE_G", os.environ.get("DALI_FISHTANK_WB_G", 0.98)),
                        0.98,
                    ),
                ),
            ),
            max(
                0.5,
                min(
                    1.8,
                    safe_float(
                        os.environ.get("DALI_FISHTANK_WHITE_BALANCE_B", os.environ.get("DALI_FISHTANK_WB_B", 1.06)),
                        1.06,
                    ),
                ),
            ),
        )
        self.layer_weight_particles = max(
            0.1,
            min(2.0, safe_float(os.environ.get("DALI_FISHTANK_LAYER_WEIGHT_PARTICLES", 0.58), 0.58)),
        )
        self.layer_weight_rd = max(
            0.1,
            min(2.0, safe_float(os.environ.get("DALI_FISHTANK_LAYER_WEIGHT_RD", 1.0), 1.0)),
        )
        self.layer_weight_volume = max(
            0.1,
            min(2.5, safe_float(os.environ.get("DALI_FISHTANK_LAYER_WEIGHT_VOLUME", 1.15), 1.15)),
        )
        if preset == "cathedral_soft":
            self.exposure_base = 1.45
            self.bloom_strength = 0.52
            self.contrast_base = 1.08
            self.saturation_base = 1.06
            self.palette_mode = "dusk"
            self.layer_weight_particles = 0.5
            self.layer_weight_rd = 1.0
            self.layer_weight_volume = 1.2
        elif self.work_mode_enabled:
            self.exposure_base = 1.0
            self.bloom_strength = min(self.bloom_strength, 0.12)
            self.contrast_base = min(self.contrast_base, 0.96)
            self.saturation_base = min(self.saturation_base, 0.92)
            if "DALI_FISHTANK_PALETTE_MODE" not in os.environ:
                self.palette_mode = "mono"
            self.layer_weight_particles = min(self.layer_weight_particles, 0.92)
            self.layer_weight_rd = min(self.layer_weight_rd, 0.2)
            self.layer_weight_volume = min(self.layer_weight_volume, 0.18)
        self.debug_luma = _env_truthy("DALI_FISHTANK_DEBUG_LUMA", "0")
        self.rd_enabled = _env_truthy("DALI_FISHTANK_RD_ENABLED", "1")
        self.vol_enabled = _env_truthy("DALI_FISHTANK_VOL_ENABLED", "1")
        self.temporal_enabled = _env_truthy("DALI_FISHTANK_TEMPORAL_ENABLED", "1")
        if self.work_mode_enabled:
            self.rd_enabled = False
            self.vol_enabled = False
            self.temporal_enabled = False
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
        if preset == "cathedral_soft":
            self.temporal_alpha_base = 0.93
        self.temporal_alpha = float(self.temporal_alpha_base)
        self.vol_luminance_mean = 0.0
        self._motion_scalar = 0.0
        self.luminance_mean = 0.0
        self.luminance_max = 0.0
        self.clipped_fraction_est = 0.0
        self._last_rd_step_ts = time.monotonic()
        self._rd_inject_until = 0.0
        self._rd_inject_seed = 0.0
        self._rd_mutation = random.Random()
        self._last_control_file_ts = 0.0
        self._control_file_cache: dict[str, dict[str, float]] = {}

        self.particles_target = int(
            min(
                self.agent_count,
                max(self.min_agent_count, int(safe_float(os.environ.get("DALI_FISHTANK_PARTICLES_TARGET", self.agent_count)))),
            )
        )
        self.particles_visible = int(self.particles_target)
        self._particles_target_base = int(self.particles_target)
        self._vol_steps_base = int(self.vol_steps)
        self.load_shed_active = False
        self.shed_reason = ""
        self.lease_mode = "exclusive"
        self.inference_quiesced = False
        self.idle_mode_enabled = False
        self.idle_trigger_source = "internal"
        self.idle_triggered_at = ""
        self.display_mode_active = True
        self.idle_inhibit_enabled = False
        self.display_inhibitor_active = False
        self.inhibitor_backend = "none"
        self.features: dict[str, dict[str, Any]] = {}
        self.features_masked: list[str] = []
        self.novelty_seed_source = "mixed"
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
        self.identity_profile = str(os.environ.get("DALI_FISHTANK_IDENTITY_PROFILE", "dali") or "dali").strip().lower()
        self.activity_snapshot: dict[str, Any] = {}
        self.activity_signal = 0.0
        self.agent_activity_level = 0.0
        self.agent_count_active = 0
        self.coordination_density = 0.0
        self.routing_activity = 0.0
        self.interaction_activity = 0.0
        self.memory_activity = 0.0
        self.heavy_inference_suppressed = False
        self.semantic_activity_source_summary = ""
        self.mirror_state = MirrorState()
        self.mirror_state_inference: dict[str, str] = {}
        self.cadence_phase: dict[str, float] = {}
        self.cadence_modulation: dict[str, float] = {}
        self.motif_weights: dict[str, float] = {
            "cathedral": 0.92,
            "clockwork_eye": 0.88,
            "dream_attractor": 0.82,
            "murmuration": 0.72,
            "neural_garden": 0.80,
            "slime_trail": 0.65,
            "stained_glass": 0.86,
            "tracer_dust": 0.52,
        }
        self.motif_activation: dict[str, float] = {}
        self.novel_layer_activation: dict[str, float] = {}
        self.wild_layer_activation: dict[str, float] = {}
        self.state_hue_mix: dict[str, Any] = {}
        self.ecosystem_state: dict[str, Any] = {}
        self.scene_attractors: dict[str, dict[str, float]] = {}
        self.colony_memory_state: dict[str, float] = {
            "colony_memory_level": 0.0,
            "route_reinforcement": 0.0,
            "dormant_zone_ratio": 0.0,
            "scar_tissue_intensity": 0.0,
            "repair_zone_intensity": 0.0,
            "stabilized_habitat_ratio": 0.0,
            "ecological_persistence": 0.0,
            "memory_flux": 0.0,
        }
        self.collapse_visual_intensity = 0.0
        self.repair_visual_intensity = 0.0
        self._dreamscape_session_anchor_mono = time.monotonic()
        self._dreamscape_session_seconds = 0.0

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
        if self.work_mode_enabled:
            self._init_work_mode_state()
            return
        rng = np.random.default_rng(42)
        self.positions = rng.uniform(-1.0, 1.0, size=(self.agent_count, 2)).astype("float32")
        self.velocities = rng.normal(0.0, 0.01, size=(self.agent_count, 2)).astype("float32")

    def _init_work_mode_state(self) -> None:
        if np is None:
            raise GPUUnavailableError("numpy is required for work mode consciousness mirror")
        grid_h, grid_w = self._work_grid_shape
        rng = np.random.default_rng(int(time.time()) & 0xFFFF)
        density = max(0.0002, min(0.08, safe_float(os.environ.get("DALI_FISHTANK_WORK_CA_DENSITY", 0.012), 0.012)))
        self._work_ca_grid = np.zeros((grid_h, grid_w), dtype="uint8")
        self._work_branch_dir_row = np.zeros((grid_h, grid_w), dtype="float32")
        self._work_branch_dir_col = np.zeros((grid_h, grid_w), dtype="float32")
        cluster_radius = max(2, min(6, int(safe_float(os.environ.get("DALI_FISHTANK_WORK_SEED_RADIUS", 3), 3))))
        for _ in range(self._work_seed_clusters):
            center_r = int(rng.integers(cluster_radius, max(cluster_radius + 1, grid_h - cluster_radius)))
            center_c = int(rng.integers(cluster_radius, max(cluster_radius + 1, grid_w - cluster_radius)))
            patch_h = min(grid_h, (cluster_radius * 2) + 1)
            patch_w = min(grid_w, (cluster_radius * 2) + 1)
            patch = (rng.random((patch_h, patch_w)) < density * 4.0).astype("uint8")
            r0 = max(0, center_r - cluster_radius)
            c0 = max(0, center_c - cluster_radius)
            r1 = min(grid_h, r0 + patch_h)
            c1 = min(grid_w, c0 + patch_w)
            self._work_ca_grid[r0:r1, c0:c1] = np.maximum(self._work_ca_grid[r0:r1, c0:c1], patch[: r1 - r0, : c1 - c0])
            base_angle = float(rng.random() * math.tau)
            self._work_branch_dir_row[r0:r1, c0:c1] = math.sin(base_angle)
            self._work_branch_dir_col[r0:r1, c0:c1] = math.cos(base_angle)
            self._stamp_work_branch_seed(center_r, center_c, base_angle=base_angle)
        if int(self._work_ca_grid.sum()) < 6:
            self._stamp_work_branch_seed(grid_h // 2, grid_w // 2, base_angle=0.0)
        self._work_ca_age = np.zeros((grid_h, grid_w), dtype="float32")
        self._work_render_grid = self._work_ca_grid.astype("float32")
        previous_state = load_json(getattr(self, "output_path", FISHTANK_STATE_PATH), {})
        previous_ca = previous_state.get("cellular_automata", {}) if isinstance(previous_state, dict) else {}
        growth_memory_cap = float(getattr(self, "_work_growth_memory_cap", 0.045) or 0.045)
        self._work_growth_memory = max(
            0.0,
            min(
                growth_memory_cap,
                safe_float(previous_ca.get("growth_memory", 0.0), 0.0),
            ),
        )
        self._work_growth_samples = max(0, int(previous_ca.get("growth_samples", 0) or 0))
        self._work_gpu_util_ema = clamp01(safe_float(previous_ca.get("gpu_util_ema", 0.0), 0.0))
        self._work_ca_tick = 0
        self.positions = np.zeros((self.agent_count, 2), dtype="float32")
        self.velocities = np.zeros((self.agent_count, 2), dtype="float32")
        self._work_step_accumulator = 0.0
        self._sync_work_mode_particles(seed_jitter=True)

    def _stamp_work_branch_seed(self, center_r: int, center_c: int, *, base_angle: float) -> None:
        if np is None:
            return
        grid_h, grid_w = self._work_ca_grid.shape
        branch_length = int(getattr(self, "_work_branch_length", 12) or 12)
        branch_specs = (
            (base_angle, max(12, branch_length)),
            (base_angle + 0.38, max(3, branch_length // 4)),
            (base_angle - 0.38, max(3, branch_length // 4)),
        )
        for angle, branch_len in branch_specs:
            direction_r = math.sin(angle)
            direction_c = math.cos(angle)
            for step in range(branch_len + 1):
                row = int(round(center_r + (direction_r * step)))
                col = int(round(center_c + (direction_c * step)))
                if 0 <= row < grid_h and 0 <= col < grid_w:
                    self._work_ca_grid[row, col] = 1
                    self._work_branch_dir_row[row, col] = direction_r
                    self._work_branch_dir_col[row, col] = direction_c

    def _sync_work_mode_particles(self, *, seed_jitter: bool = False) -> None:
        if np is None or not self.work_mode_enabled:
            return
        grid_h, grid_w = self._work_grid_shape
        alive = np.argwhere(self._work_ca_grid > 0)
        if alive.size == 0:
            self._work_ca_grid[grid_h // 2, grid_w // 2] = 1
            alive = np.argwhere(self._work_ca_grid > 0)
        alive_count = int(min(len(alive), self.agent_count))
        if alive_count > 0:
            alive = alive[:alive_count]
            x = ((alive[:, 1].astype("float32") + 0.5) / max(1.0, float(grid_w))) * 2.0 - 1.0
            y = 1.0 - (((alive[:, 0].astype("float32") + 0.5) / max(1.0, float(grid_h))) * 2.0)
            points = np.stack((x, y), axis=1)
            if seed_jitter:
                points += np.random.default_rng(7).normal(0.0, 0.0015, size=points.shape).astype("float32")
            self.positions[:alive_count] = points
        if alive_count < self.agent_count:
            self.positions[alive_count:] = np.array([3.0, 3.0], dtype="float32")
            self.velocities[alive_count:] = 0.0
        self.particles_visible = max(64, alive_count)

    def _update_work_mode_render_grid(self) -> None:
        if np is None or not self.work_mode_enabled:
            return
        target = self._work_ca_grid.astype("float32")
        current = getattr(self, "_work_render_grid", None)
        if current is None or current.shape != target.shape:
            self._work_render_grid = target.copy()
            return
        smoothing = float(self._work_render_smoothing)
        self._work_render_grid = (current * (1.0 - smoothing)) + (target * smoothing)
        self._work_render_grid[self._work_render_grid < 0.015] = 0.0

    def _work_mode_step(self, dt: float) -> None:
        if np is None or not self.work_mode_enabled:
            return
        self._work_step_accumulator += max(0.0, float(dt))
        if self._work_step_accumulator < self._work_step_interval_s:
            return
        step_dt = self._work_step_accumulator
        self._work_step_accumulator = 0.0
        grid = self._work_ca_grid
        dir_row = self._work_branch_dir_row
        dir_col = self._work_branch_dir_col
        branch_persistence = float(getattr(self, "_work_branch_persistence", 0.9) or 0.9)
        branch_thickness_prob = float(getattr(self, "_work_branch_thickness_prob", 0.03) or 0.03)
        novel_branch_rate = float(getattr(self, "_work_novel_branch_rate", 0.06) or 0.06)
        branch_turn_std = float(getattr(self, "_work_branch_turn_std", 0.08) or 0.08)
        permanent_core = (grid == 1) & (self._work_ca_age >= self._work_core_age_threshold)
        neighbors = (
            np.roll(grid, 1, 0)
            + np.roll(grid, -1, 0)
            + np.roll(grid, 1, 1)
            + np.roll(grid, -1, 1)
            + np.roll(np.roll(grid, 1, 0), 1, 1)
            + np.roll(np.roll(grid, 1, 0), -1, 1)
            + np.roll(np.roll(grid, -1, 0), 1, 1)
            + np.roll(np.roll(grid, -1, 0), -1, 1)
        )
        survive = ((grid == 1) & ((neighbors == 2) | (neighbors == 3))).astype("uint8")
        birth = ((grid == 0) & (neighbors == 3)).astype("uint8")
        next_grid = np.maximum(survive, birth)
        next_dir_row = dir_row * survive.astype("float32")
        next_dir_col = dir_col * survive.astype("float32")
        growth_phase = clamp01(float(self._work_ca_tick) / max(1.0, float(self._work_growth_target_ticks)))
        mutation = (
            0.000015
            + (growth_phase * 0.00011)
            + (self.control_values.get("curiosity_impulse", 0.0) * 0.00025)
            + (self.activity_signal * 0.00008)
        )
        rng = np.random.default_rng((self.frame_index + 1) * 17)
        gpu_util_now = clamp01(float(getattr(self.signals, "gpu_util", 0.0) or 0.0))
        spike = max(0.0, gpu_util_now - max(self._work_gpu_util_ema, self._work_growth_spike_floor))
        self._work_gpu_util_ema = clamp01((self._work_gpu_util_ema * 0.92) + (gpu_util_now * 0.08))
        growth_gain = 0.0
        if spike > 0.0:
            growth_gain = float(rng.random()) * spike * self._work_growth_sample_scale
            self._work_growth_memory = min(self._work_growth_memory_cap, self._work_growth_memory + growth_gain)
            self._work_growth_samples += 1
        self._work_growth_last_gain = growth_gain
        frontier = ((neighbors > 0) & (neighbors < 5) & (grid == 0))
        flips = ((rng.random(next_grid.shape) < mutation) & frontier).astype("uint8")
        next_grid = np.where(flips > 0, 1, next_grid).astype("uint8")
        if bool(flips.any()):
            neighbor_dir_row = (
                np.roll(dir_row, 1, 0)
                + np.roll(dir_row, -1, 0)
                + np.roll(dir_row, 1, 1)
                + np.roll(dir_row, -1, 1)
            ) / 4.0
            neighbor_dir_col = (
                np.roll(dir_col, 1, 0)
                + np.roll(dir_col, -1, 0)
                + np.roll(dir_col, 1, 1)
                + np.roll(dir_col, -1, 1)
            ) / 4.0
            next_dir_row = np.where(flips > 0, neighbor_dir_row, next_dir_row).astype("float32")
            next_dir_col = np.where(flips > 0, neighbor_dir_col, next_dir_col).astype("float32")
        matured = (grid == 1) & (self._work_ca_age > (4.0 + (growth_phase * 10.0)))
        if bool(matured.any()):
            mitosis_rate = 0.000002 + (growth_phase * 0.00004) + (self.activity_signal * 0.00003) + (self._work_growth_memory * 0.00045)
            empty = next_grid == 0
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
                budding = np.roll(np.roll(matured, dr, axis=0), dc, axis=1)
                bud_mask = budding & empty & (rng.random(next_grid.shape) < mitosis_rate)
                next_grid = np.where(bud_mask, 1, next_grid).astype("uint8")
                next_dir_row = np.where(bud_mask, np.roll(np.roll(dir_row, dr, axis=0), dc, axis=1), next_dir_row).astype("float32")
                next_dir_col = np.where(bud_mask, np.roll(np.roll(dir_col, dr, axis=0), dc, axis=1), next_dir_col).astype("float32")
                empty = next_grid == 0
        alive_ratio = float(next_grid.mean())
        target_alive_ratio = 0.0012 + (self._work_target_alive_ratio * growth_phase) + self._work_growth_memory
        if alive_ratio < target_alive_ratio:
            novelty_pulses = min(
                self._work_novelty_pulse_limit,
                1 + int(self.control_values.get("curiosity_impulse", 0.0) > 0.92),
            )
            alive_cells = np.argwhere(grid > 0)
            for _ in range(novelty_pulses):
                if alive_cells.size > 0:
                    anchor_row, anchor_col = alive_cells[int(rng.integers(0, len(alive_cells)))]
                    base_dir_row = float(dir_row[int(anchor_row), int(anchor_col)])
                    base_dir_col = float(dir_col[int(anchor_row), int(anchor_col)])
                    if abs(base_dir_row) + abs(base_dir_col) > 0.001:
                        base_angle = math.atan2(base_dir_row, base_dir_col)
                        angle = (base_angle * branch_persistence) + (
                            (base_angle + float(rng.normal(0.0, 0.12))) * (1.0 - branch_persistence)
                        )
                    else:
                        angle = float(rng.random() * math.tau)
                    branch_len_cap = max(6, self._work_branch_length + int(round(self._work_growth_memory * 420.0)))
                    branch_len = int(rng.integers(max(6, int(branch_len_cap * 0.7)), branch_len_cap + 1))
                    direction_r = math.sin(angle)
                    direction_c = math.cos(angle)
                    tip_r = int(
                        max(
                            0,
                            min(
                                next_grid.shape[0] - 1,
                                anchor_row + round(direction_r * branch_len),
                            ),
                        )
                    )
                    tip_c = int(
                        max(
                            0,
                            min(
                                next_grid.shape[1] - 1,
                                anchor_col + round(direction_c * branch_len),
                            ),
                        )
                    )
                    branch_steps = max(abs(tip_r - int(anchor_row)), abs(tip_c - int(anchor_col)), 1)
                    for step in range(branch_steps + 1):
                        t = step / branch_steps
                        row = int(round((1.0 - t) * float(anchor_row) + t * float(tip_r)))
                        col = int(round((1.0 - t) * float(anchor_col) + t * float(tip_c)))
                        next_grid[row, col] = 1
                        next_dir_row[row, col] = direction_r
                        next_dir_col[row, col] = direction_c
                        if float(rng.random()) < (branch_thickness_prob * max(0.0, 1.0 - t)):
                            side_angle = angle + (math.pi / 2.0 if float(rng.random()) < 0.5 else -math.pi / 2.0)
                            side_row = int(round(row + math.sin(side_angle)))
                            side_col = int(round(col + math.cos(side_angle)))
                            if 0 <= side_row < next_grid.shape[0] and 0 <= side_col < next_grid.shape[1]:
                                next_grid[side_row, side_col] = 1
                                next_dir_row[side_row, side_col] = direction_r
                                next_dir_col[side_row, side_col] = direction_c
                        if step > max(3, branch_steps // 2) and float(rng.random()) < (novel_branch_rate * (0.18 + (growth_phase * 0.35))):
                            twig_angle = angle + float(rng.normal(0.0, branch_turn_std * (0.7 + (growth_phase * 0.4))))
                            twig_len = int(rng.integers(3, max(4, branch_len_cap // 2) + 1))
                            twig_dir_r = math.sin(twig_angle)
                            twig_dir_c = math.cos(twig_angle)
                            for twig_step in range(1, twig_len + 1):
                                twig_row = int(round(row + (twig_dir_r * twig_step)))
                                twig_col = int(round(col + (twig_dir_c * twig_step)))
                                if 0 <= twig_row < next_grid.shape[0] and 0 <= twig_col < next_grid.shape[1]:
                                    next_grid[twig_row, twig_col] = 1
                                    next_dir_row[twig_row, twig_col] = twig_dir_r
                                    next_dir_col[twig_row, twig_col] = twig_dir_c
                    pulse_r = tip_r
                    pulse_c = tip_c
                else:
                    pulse_r = int(rng.integers(0, next_grid.shape[0]))
                    pulse_c = int(rng.integers(0, next_grid.shape[1]))
                if 0 <= pulse_r < next_grid.shape[0] and 0 <= pulse_c < next_grid.shape[1] and neighbors[pulse_r, pulse_c] > 0:
                    next_grid[pulse_r, pulse_c] = 1
                if self._work_pulses_enabled:
                    self._work_recent_pulses.append(
                        {
                            "row": float(pulse_r),
                            "col": float(pulse_c),
                            "life": 1.0,
                        }
                    )
            alive_ratio = float(next_grid.mean())
        upper_bound = max(0.012, target_alive_ratio * 1.18)
        if alive_ratio > upper_bound:
            thinning = rng.random(next_grid.shape) < min(0.3, 0.03 + ((alive_ratio - upper_bound) * 3.0))
            next_grid = np.where(thinning & (next_grid > 0), 0, next_grid).astype("uint8")
            alive_ratio = float(next_grid.mean())
        next_grid = np.where(permanent_core, 1, next_grid).astype("uint8")
        cull_isolates = (next_grid > 0) & (neighbors <= 1) & (self._work_ca_age < self._work_core_age_threshold)
        next_grid = np.where(cull_isolates, 0, next_grid).astype("uint8")
        next_dir_row = np.where(next_grid > 0, next_dir_row, 0.0).astype("float32")
        next_dir_col = np.where(next_grid > 0, next_dir_col, 0.0).astype("float32")
        alive_ratio = float(next_grid.mean())
        age_increment = max(0.03, step_dt * 0.12)
        self._work_ca_age = np.where(next_grid > 0, self._work_ca_age + age_increment, 0.0).astype("float32")
        self._work_ca_grid = next_grid
        self._work_branch_dir_row = next_dir_row
        self._work_branch_dir_col = next_dir_col
        self._work_ca_tick += 1
        self.shader_params["luminosity"] = clamp01(0.14 + alive_ratio * 1.25 + (growth_phase * 0.18))
        self.shader_params["turbulence"] = clamp01(0.03 + float(flips.mean()) * 24.0 + (growth_phase * 0.1))
        self.shader_params["vortex"] = clamp01(0.12 + self.signals.arousal * 0.35)
        self.shader_params["cloud"] = clamp01((alive_ratio * 0.85) + (growth_phase * 0.16))
        self.shader_params["nebula"] = clamp01(0.04 + alive_ratio * 0.95 + (growth_phase * 0.12))
        self.shader_params["velocity"] = clamp01(0.08 + self.activity_signal * 0.4)
        decayed_pulses: list[dict[str, float]] = []
        for pulse in self._work_recent_pulses:
            next_life = float(pulse.get("life", 0.0)) - max(0.0015, step_dt * 0.01)
            if next_life > 0.0:
                pulse["life"] = next_life
                decayed_pulses.append(pulse)
        self._work_recent_pulses = decayed_pulses[:24]
        self._sync_work_mode_particles()

    def _work_mode_preview_rows(self, *, max_rows: int = 24, max_cols: int = 48) -> list[str]:
        if np is None or not self.work_mode_enabled:
            return []
        grid = self._work_ca_grid
        grid_h, grid_w = grid.shape
        row_step = max(1, int(math.ceil(grid_h / max(1, max_rows))))
        col_step = max(1, int(math.ceil(grid_w / max(1, max_cols))))
        preview = grid[::row_step, ::col_step]
        return ["".join("#" if int(cell) else "." for cell in row) for row in preview[:max_rows]]

    def _ensure_fantasy_landscape_state(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        if self._fantasy_scene_state and self._fantasy_scene_dimensions == (width, height):
            return
        rng = random.Random(7331)
        self._fantasy_scene_dimensions = (width, height)
        self._fantasy_scene_started_ts = time.monotonic()
        self._fantasy_scene_state = {
            "stars": [
                {
                    "x": rng.uniform(0.03, 0.97),
                    "y": rng.uniform(0.03, 0.47),
                    "size": rng.uniform(0.7, 2.1),
                    "twinkle": rng.uniform(0.4, 1.8),
                    "phase": rng.uniform(0.0, math.tau),
                    "bright": rng.random() < 0.18,
                }
                for _ in range(124)
            ],
            "clouds": [
                {
                    "x": base_x,
                    "y": base_y,
                    "scale": scale,
                    "speed": rng.uniform(0.0014, 0.0044),
                    "phase": rng.uniform(0.0, math.tau),
                    "puffs": [
                        (
                            rng.uniform(-0.075, 0.075) * scale,
                            rng.uniform(-0.022, 0.024) * scale,
                            rng.uniform(0.045, 0.095) * scale,
                            rng.uniform(0.026, 0.055) * scale,
                        )
                        for _ in range(4 + (idx % 2))
                    ],
                }
                for idx, (base_x, base_y, scale) in enumerate(
                    (
                        (-0.08, 0.115, 0.84),
                        (0.82, 0.15, 0.92),
                        (0.18, 0.24, 0.68),
                        (0.64, 0.22, 0.74),
                    )
                )
            ],
            "mist_bands": [
                {
                    "y": rng.uniform(0.56, 0.9),
                    "thickness": rng.uniform(0.03, 0.08),
                    "speed": rng.uniform(0.001, 0.003),
                    "phase": rng.uniform(0.0, math.tau),
                    "alpha": rng.uniform(0.28, 0.72),
                }
                for _ in range(5)
            ],
            "fireflies": [
                {
                    "x": rng.uniform(0.1, 0.9),
                    "y": rng.uniform(0.68, 0.93),
                    "drift_x": rng.uniform(0.008, 0.028),
                    "drift_y": rng.uniform(0.004, 0.015),
                    "phase": rng.uniform(0.0, math.tau),
                    "speed": rng.uniform(0.18, 0.42),
                    "radius": rng.uniform(1.0, 2.6),
                }
                for _ in range(20)
            ],
            "ducks": [
                {
                    "phase": rng.uniform(0.0, 1.0),
                    "speed": rng.uniform(0.07, 0.11),
                    "lane": rng.uniform(0.06, 0.94),
                    "wing_phase": rng.uniform(0.0, math.tau),
                    "heading": -1.0 if rng.random() < 0.5 else 1.0,
                    "size": rng.uniform(0.92, 1.18),
                    "pond_jitter": rng.uniform(0.8, 1.2),
                }
                for _ in range(4)
            ],
            "fish": [
                {
                    "x": rng.uniform(0.36, 0.62),
                    "y": rng.uniform(0.8, 0.89),
                    "speed": rng.uniform(0.07, 0.14),
                    "depth": rng.uniform(0.0, 1.0),
                    "phase": rng.uniform(0.0, math.tau),
                    "heading": -1.0 if rng.random() < 0.5 else 1.0,
                    "lane": rng.uniform(0.0, 1.0),
                }
                for _ in range(7)
            ],
            "dragon": {
                "phase": rng.uniform(0.0, math.tau),
                "speed": rng.uniform(0.014, 0.022),
                "lane": rng.uniform(0.0, 1.0),
                "scale": rng.uniform(1.0, 1.35),
                "heading": -1.0 if rng.random() < 0.5 else 1.0,
            },
            "window_phase": rng.uniform(0.0, math.tau),
            "lantern_phase": rng.uniform(0.0, math.tau),
            "smoke_phase": rng.uniform(0.0, math.tau),
        }

    def _render_fantasy_landscape_scene(self, canvas: Any, width: int, height: int, now: float) -> None:
        self._ensure_fantasy_landscape_state(width, height)
        state = self._fantasy_scene_state
        scene_age = max(0.0, now - self._fantasy_scene_started_ts)
        t = scene_age * self._work_scene_time_scale
        growth_memory = float(getattr(self, "_work_growth_memory", 0.0) or 0.0)
        curiosity = float(getattr(self, "control_values", {}).get("curiosity_impulse", 0.0) or 0.0)
        gpu_util = clamp01(float(getattr(self.signals, "gpu_util", 0.0) or 0.0))
        horizon_y = int(height * 0.63)
        pond_center_x = width * 0.46
        pond_center_y = height * 0.846
        pond_rx = width * 0.152
        pond_ry = height * 0.078

        def mix_color(start: tuple[int, int, int], end: tuple[int, int, int], ratio: float) -> str:
            ratio = clamp01(ratio)
            r = int(start[0] + ((end[0] - start[0]) * ratio))
            g = int(start[1] + ((end[1] - start[1]) * ratio))
            b = int(start[2] + ((end[2] - start[2]) * ratio))
            return f"#{r:02x}{g:02x}{b:02x}"

        def draw_reflection_lines(center_x: float, center_y: float, span_x: float, span_y: float, color: str, density: int = 6) -> None:
            for idx in range(density):
                ratio = idx / max(1, density - 1)
                line_y = center_y + ((ratio - 0.5) * span_y)
                line_w = span_x * (1.0 - (0.55 * abs((ratio * 2.0) - 1.0)))
                jitter = math.sin((t * 0.9) + (idx * 0.6)) * width * 0.003
                canvas.create_line(center_x - line_w * 0.5 + jitter, line_y, center_x + line_w * 0.5 + jitter, line_y, fill=color, width=1, tags="atmo")

        def draw_splash(x: float, y: float, scale: float, energy: float) -> None:
            energy = clamp01(energy)
            splash_r = width * (0.006 + (0.01 * energy)) * scale
            canvas.create_arc(x - splash_r, y - splash_r, x + splash_r, y + splash_r, start=15, extent=150, style="arc", outline="#cbe7f2", width=1, tags="atmo")
            canvas.create_arc(x - splash_r * 0.8, y - splash_r * 0.35, x + splash_r * 0.8, y + splash_r * 1.1, start=200, extent=120, style="arc", outline="#9ed5ea", width=1, tags="atmo")
            for idx in range(3):
                angle = (-0.6 + (idx * 0.6)) + (energy * 0.1)
                drop_x = x + math.sin(angle) * splash_r * (0.8 + (idx * 0.18))
                drop_y = y - splash_r * (0.35 + (idx * 0.22))
                drop_r = max(1.5, splash_r * 0.16)
                canvas.create_oval(drop_x - drop_r, drop_y - drop_r, drop_x + drop_r, drop_y + drop_r, fill="#d9f3ff", outline="", tags="atmo")

        def draw_duck(x: float, y: float, scale: float, wing_lift: float, heading: float, *, on_water: bool = False, running: bool = False) -> None:
            body_w = width * 0.013 * scale
            body_h = height * 0.0095 * scale
            neck_len = body_h * 1.05
            head_r = body_h * 0.56
            duck_fill = "#ece7d8" if on_water else "#f0ece2"
            belly_fill = "#d8d0bc"
            wing_reach = body_w * (0.95 + (1.1 * abs(wing_lift)))
            wing_height = body_h * (0.3 + (1.05 * max(0.0, wing_lift)))
            canvas.create_polygon(
                [
                    (x - body_w * 1.05, y + body_h * 0.12),
                    (x - body_w * 0.7, y - body_h * 0.52),
                    (x + body_w * 0.2, y - body_h * 0.72),
                    (x + body_w * 0.82, y - body_h * 0.2),
                    (x + body_w * 0.9, y + body_h * 0.18),
                    (x + body_w * 0.24, y + body_h * 0.55),
                    (x - body_w * 0.55, y + body_h * 0.48),
                ],
                fill=duck_fill,
                outline="#8b8575",
                width=1,
                smooth=True,
                splinesteps=14,
                tags="scene",
            )
            canvas.create_polygon([(x - body_w * 0.1, y), (x - wing_reach, y - wing_height), (x - body_w * 0.2, y + body_h * 0.12)], fill="#f4f0e7", outline="#9b9484", width=1, tags="scene")
            canvas.create_polygon([(x + body_w * 0.05, y - body_h * 0.06), (x + wing_reach * 0.92, y - wing_height * 0.86), (x + body_w * 0.3, y + body_h * 0.16)], fill="#f4f0e7", outline="#9b9484", width=1, tags="scene")
            neck_x = x + (body_w * 0.52 * heading)
            neck_y = y - body_h * 0.42
            canvas.create_line(x + body_w * 0.18 * heading, y - body_h * 0.18, neck_x, neck_y - neck_len * 0.65, fill="#8b8575", width=max(1, int(scale)), smooth=True, splinesteps=10, tags="scene")
            head_x = neck_x + (body_w * 0.28 * heading)
            head_y = neck_y - neck_len * 0.74
            canvas.create_oval(head_x - head_r, head_y - head_r, head_x + head_r, head_y + head_r, fill=duck_fill, outline="#8b8575", width=1, tags="scene")
            canvas.create_polygon([(head_x + head_r * 0.82 * heading, head_y - head_r * 0.1), (head_x + head_r * 1.95 * heading, head_y + head_r * 0.12), (head_x + head_r * 0.86 * heading, head_y + head_r * 0.38)], fill="#e0a458", outline="", tags="scene")
            canvas.create_polygon([(x - body_w * 1.06, y + body_h * 0.1), (x - body_w * 1.42, y - body_h * 0.02), (x - body_w * 1.02, y - body_h * 0.22)], fill=belly_fill, outline="#8b8575", width=1, tags="scene")
            if running:
                stride = body_w * 0.32
                canvas.create_line(x - stride, y + body_h * 0.52, x - stride * 1.25, y + body_h * 1.26, fill="#e08f44", width=2, tags="scene")
                canvas.create_line(x, y + body_h * 0.52, x + stride * 0.12, y + body_h * 1.18, fill="#e08f44", width=2, tags="scene")
            if on_water:
                draw_reflection_lines(x, y + body_h * 1.08, body_w * 3.0, height * 0.008, "#b9d7e6", density=4)

        def draw_dragon(x: float, y: float, scale: float, fire_strength: float) -> None:
            body_len = width * 0.068 * scale
            body_h = height * 0.02 * scale
            wing_lift = math.sin((t * 6.3) + float(state.get("dragon", {}).get("phase", 0.0) or 0.0)) * height * 0.022 * scale
            back_points: list[float] = []
            for idx in range(5):
                ratio = idx / 4.0
                seg_x = x - body_len * 0.72 + (body_len * ratio * 1.45)
                seg_y = y + math.sin((ratio * math.pi * 2.4) + (t * 1.3)) * body_h * (0.28 + ratio * 0.18)
                back_points.extend((seg_x, seg_y))
            canvas.create_line(back_points, smooth=True, splinesteps=18, fill="#424a67", width=max(2, int(width * 0.0031 * scale)), tags="scene")
            canvas.create_polygon([(x - body_len * 0.08, y - body_h * 0.12), (x - body_len * 0.92, y - wing_lift), (x - body_len * 0.26, y + body_h * 0.26)], fill="#4d5677", outline="#7785a6", width=1, tags="scene")
            canvas.create_polygon([(x + body_len * 0.06, y - body_h * 0.02), (x + body_len * 0.96, y - wing_lift * 0.82), (x + body_len * 0.28, y + body_h * 0.34)], fill="#4d5677", outline="#7785a6", width=1, tags="scene")
            for idx in range(4):
                spike_x = x - body_len * 0.4 + (body_len * 0.28 * idx)
                spike_y = y - body_h * (0.58 + (0.16 * math.sin((t * 2.0) + idx)))
                canvas.create_polygon([(spike_x - body_h * 0.4, y - body_h * 0.12), (spike_x, spike_y), (spike_x + body_h * 0.4, y - body_h * 0.08)], fill="#67759c", outline="", tags="scene")
            canvas.create_polygon([(x + body_len * 0.52, y - body_h * 0.12), (x + body_len * 0.9, y - body_h * 0.42), (x + body_len * 0.88, y + body_h * 0.12)], fill="#5b627e", outline="#7d87a9", width=1, tags="scene")
            if fire_strength > 0.0:
                fire_len = width * (0.06 + (0.08 * fire_strength)) * scale
                canvas.create_polygon([(x + body_len * 0.9, y - body_h * 0.1), (x + body_len * 0.9 + fire_len, y - body_h * (0.95 + fire_strength)), (x + body_len * 0.9 + fire_len * 0.55, y), (x + body_len * 0.9 + fire_len, y + body_h * (0.95 + fire_strength))], fill="#ff7a2f", outline="#ffd36d", width=1, tags="atmo")
                canvas.create_polygon([(x + body_len * 0.92, y - body_h * 0.06), (x + body_len * 0.92 + fire_len * 0.72, y - body_h * (0.44 + fire_strength * 0.42)), (x + body_len * 0.92 + fire_len * 0.36, y), (x + body_len * 0.92 + fire_len * 0.72, y + body_h * (0.44 + fire_strength * 0.42))], fill="#ffd36a", outline="", tags="atmo")

        def draw_smoke_plume(chimney_top_x: float, chimney_top_y: float) -> None:
            smoke_phase = (t * 0.12) + float(state.get("smoke_phase", 0.0) or 0.0)
            for idx in range(7):
                plume_age = (smoke_phase + (idx * 0.17)) % 1.0
                sway = math.sin((plume_age * math.tau * 0.75) + idx * 0.8) * width * (0.005 + plume_age * 0.012)
                sx = chimney_top_x + sway
                sy = chimney_top_y - (height * (0.014 + plume_age * 0.12))
                sr = max(4.0, width * (0.004 + plume_age * 0.007))
                glow = 1.0 - plume_age
                fill = mix_color((88, 100, 118), (186, 196, 214), 0.35 + glow * 0.38)
                outline = mix_color((64, 76, 92), (146, 158, 176), 0.3 + glow * 0.4)
                canvas.create_oval(sx - sr, sy - sr, sx + sr, sy + sr, fill=fill, outline=outline, width=1, tags="atmo")
                if idx % 2 == 0:
                    canvas.create_oval(sx - sr * 1.4, sy - sr * 0.8, sx + sr * 1.4, sy + sr * 0.8, outline="#bbc6d5", width=1, tags="atmo")

        canvas.delete("bg")
        canvas.delete("scene")
        canvas.delete("atmo")

        top_color = (5, 10, 24)
        mid_color = (18, 32, 66)
        horizon_color = (92, 104, 138)
        dawn_glaze = (22, 58, 76)
        for idx in range(28):
            y0 = int((height / 28.0) * idx)
            y1 = int((height / 28.0) * (idx + 1))
            ratio = idx / 27.0
            if ratio < 0.48:
                band = mix_color(top_color, mid_color, ratio / 0.48)
            elif ratio < 0.84:
                band = mix_color(mid_color, horizon_color, (ratio - 0.48) / 0.36)
            else:
                band = mix_color(horizon_color, dawn_glaze, (ratio - 0.84) / 0.16)
            canvas.create_rectangle(0, y0, width, y1 + 1, fill=band, outline="", tags="bg")

        moon_x = width * 0.18
        moon_y = height * 0.19
        moon_r = min(width, height) * 0.065
        for idx, scale in enumerate((2.4, 1.85, 1.35)):
            alpha_ratio = 1.0 - (idx * 0.26)
            glow = mix_color((62, 100, 142), (150, 186, 222), alpha_ratio * 0.55)
            radius = moon_r * scale
            canvas.create_oval(moon_x - radius, moon_y - radius, moon_x + radius, moon_y + radius, fill="", outline=glow, width=1, tags="atmo")
        canvas.create_oval(moon_x - moon_r, moon_y - moon_r, moon_x + moon_r, moon_y + moon_r, fill="#f2f1e7", outline="#f8f3d0", width=1, tags="scene")

        for star in state.get("stars", []):
            twinkle = 0.55 + (0.45 * math.sin((t * star["twinkle"]) + star["phase"]))
            px = star["x"] * width
            py = star["y"] * height
            radius = star["size"] * (0.7 + (0.35 * twinkle))
            shade = mix_color((104, 126, 170), (236, 239, 255), twinkle)
            canvas.create_oval(px - radius, py - radius, px + radius, py + radius, fill=shade, outline="", tags="scene")
            if bool(star.get("bright")):
                glow = radius * 4.0
                canvas.create_line(px - glow, py, px + glow, py, fill="#9dbbe4", width=1, tags="atmo")
                canvas.create_line(px, py - glow, px, py + glow, fill="#9dbbe4", width=1, tags="atmo")

        for cloud in state.get("clouds", []):
            drift_x = ((cloud["x"] + (t * cloud["speed"])) % 1.35) - 0.18
            cx = drift_x * width
            cy = cloud["y"] * height
            cloud_tone = 0.45 + (0.2 * math.sin((t * 0.4) + cloud["phase"]))
            outline = mix_color((32, 48, 76), (74, 92, 122), cloud_tone)
            fill = mix_color((24, 38, 60), (90, 104, 136), cloud_tone)
            for puff_x, puff_y, puff_w, puff_h in cloud["puffs"]:
                x0 = cx + (puff_x * width) - (puff_w * width)
                y0 = cy + (puff_y * height) - (puff_h * height)
                x1 = cx + (puff_x * width) + (puff_w * width)
                y1 = cy + (puff_y * height) + (puff_h * height)
                canvas.create_oval(x0, y0, x1, y1, fill=fill, outline=outline, width=1, tags="scene")

        dragon = state.get("dragon", {})
        dragon_reflection_strength = 0.0
        dragon_reflection_x = pond_center_x
        if isinstance(dragon, dict):
            dragon_cycle = (t * float(dragon.get("speed", 0.018) or 0.018)) % 1.0
            if dragon_cycle < 0.56:
                progress = dragon_cycle / 0.56
                heading = float(dragon.get("heading", 1.0) or 1.0)
                dragon_x = width * (1.12 - (1.28 * progress)) if heading < 0 else width * (-0.12 + (1.28 * progress))
                dragon_y = height * (0.15 + (0.11 * float(dragon.get("lane", 0.5) or 0.5))) + math.sin((t * 0.7) + float(dragon.get("phase", 0.0) or 0.0)) * height * 0.018
                fire_strength = 0.0
                if 0.34 < progress < 0.49:
                    fire_strength = math.sin(((progress - 0.34) / 0.15) * math.pi)
                    dragon_reflection_strength = fire_strength
                    dragon_reflection_x = dragon_x + width * 0.08
                draw_dragon(dragon_x, dragon_y, float(dragon.get("scale", 1.0) or 1.0), fire_strength)

        ridge_back = [(0, horizon_y), (width * 0.08, height * 0.53), (width * 0.19, height * 0.58), (width * 0.33, height * 0.49), (width * 0.46, height * 0.57), (width * 0.62, height * 0.47), (width * 0.78, height * 0.56), (width, height * 0.5), (width, height), (0, height)]
        ridge_mid = [(0, height * 0.73), (width * 0.1, height * 0.66), (width * 0.24, height * 0.69), (width * 0.38, height * 0.61), (width * 0.52, height * 0.67), (width * 0.67, height * 0.58), (width * 0.83, height * 0.66), (width, height * 0.61), (width, height), (0, height)]
        canvas.create_polygon(ridge_back, fill="#19233e", outline="#2b375a", smooth=True, splinesteps=24, tags="scene")
        canvas.create_polygon(ridge_mid, fill="#122036", outline="#20304d", smooth=True, splinesteps=24, tags="scene")

        cave_x = width * 0.375
        cave_y = height * 0.71
        cave_w = width * 0.058
        cave_h = height * 0.042
        cave_glow = 0.5 + (0.5 * math.sin((t * 0.8) + float(state.get("lantern_phase", 0.0) or 0.0)))
        canvas.create_arc(cave_x - cave_w, cave_y - cave_h, cave_x + cave_w, cave_y + cave_h, start=0, extent=180, style="pieslice", fill="#060a12", outline="#1b2235", width=1, tags="scene")
        canvas.create_polygon([(cave_x - cave_w * 0.58, cave_y - cave_h * 0.12), (cave_x + cave_w * 0.58, cave_y - cave_h * 0.12), (cave_x + cave_w * 0.44, cave_y + cave_h * 0.4), (cave_x - cave_w * 0.44, cave_y + cave_h * 0.4)], fill=mix_color((7, 24, 30), (22, 102, 100), cave_glow * 0.3), outline="", tags="atmo")
        artifact_x = cave_x
        artifact_y = cave_y - (cave_h * 0.18)
        for idx, scale in enumerate((3.2, 2.2, 1.35)):
            radius = width * 0.008 * scale
            canvas.create_oval(artifact_x - radius, artifact_y - radius, artifact_x + radius, artifact_y + radius, outline="#3cf0de" if idx == 0 else "#2ab8c2", width=1, tags="atmo")
        canvas.create_polygon([(artifact_x, artifact_y - height * 0.016), (artifact_x - width * 0.01, artifact_y + height * 0.01), (artifact_x, artifact_y + height * 0.022), (artifact_x + width * 0.01, artifact_y + height * 0.01)], fill="#4ff0dc", outline="#a3fff2", width=1, tags="atmo")

        house_base_x = width * 0.735
        house_base_y = height * 0.792
        house_w = width * 0.145
        house_h = height * 0.145
        canvas.create_rectangle(house_base_x - house_w * 0.5, house_base_y - house_h, house_base_x + house_w * 0.5, house_base_y, fill="#31251f", outline="#5b473c", width=1, tags="scene")
        for idx in range(5):
            line_y = house_base_y - house_h + (idx + 1) * house_h * 0.17
            canvas.create_line(house_base_x - house_w * 0.48, line_y, house_base_x + house_w * 0.48, line_y, fill="#45342d", width=1, tags="scene")
        roof_left = house_base_x - house_w * 0.62
        roof_right = house_base_x + house_w * 0.62
        roof_peak_y = house_base_y - house_h - (height * 0.075)
        roof_base_y = house_base_y - house_h
        canvas.create_polygon([(roof_left, roof_base_y), (house_base_x, roof_peak_y), (roof_right, roof_base_y)], fill="#4f3027", outline="#775347", width=1, tags="scene")
        for idx in range(14):
            t0 = idx / 14.0
            t1 = (idx + 1) / 14.0
            x0 = roof_left + ((roof_right - roof_left) * t0)
            x1 = roof_left + ((roof_right - roof_left) * t1)
            crest = 1.0 - abs((((t0 + t1) * 0.5) * 2.0) - 1.0)
            top_y = roof_base_y - ((roof_base_y - roof_peak_y) * crest)
            canvas.create_polygon([(x0, roof_base_y), (x0 + (house_w * 0.006), top_y + height * 0.004), (x1 - (house_w * 0.006), top_y + height * 0.004), (x1, roof_base_y)], fill="#6d483a" if (idx % 2) == 0 else "#5c3a30", outline="#8a6659", width=1, tags="scene")
        canvas.create_line(roof_left, roof_base_y, house_base_x, roof_peak_y, fill="#9a7061", width=1, tags="scene")
        canvas.create_line(house_base_x, roof_peak_y, roof_right, roof_base_y, fill="#9a7061", width=1, tags="scene")
        chimney_x = house_base_x + house_w * 0.22
        canvas.create_rectangle(chimney_x, house_base_y - house_h - (height * 0.045), chimney_x + (house_w * 0.11), house_base_y - house_h * 0.56, fill="#3b302d", outline="#655451", width=1, tags="scene")
        draw_smoke_plume(chimney_x + (house_w * 0.055), house_base_y - house_h - (height * 0.045))
        porch_y = house_base_y
        canvas.create_rectangle(house_base_x - house_w * 0.16, porch_y - height * 0.008, house_base_x + house_w * 0.16, porch_y + height * 0.008, fill="#372920", outline="", tags="scene")
        door_w = house_w * 0.18
        door_h = house_h * 0.48
        door_x0 = house_base_x - (door_w * 0.5)
        door_y0 = house_base_y - door_h
        canvas.create_rectangle(door_x0, door_y0, door_x0 + door_w, house_base_y, fill="#2d1e17", outline="#5b4333", width=1, tags="scene")
        canvas.create_line(door_x0 + door_w * 0.5, door_y0 + height * 0.006, door_x0 + door_w * 0.5, house_base_y - height * 0.006, fill="#47352a", width=1, tags="scene")
        canvas.create_oval(door_x0 + (door_w * 0.75), door_y0 + (door_h * 0.52), door_x0 + (door_w * 0.82), door_y0 + (door_h * 0.59), fill="#d8b66b", outline="", tags="atmo")
        for offset in (-0.26, 0.12):
            wx0 = house_base_x + (house_w * offset)
            wy0 = house_base_y - house_h * 0.66
            ww = house_w * 0.16
            wh = house_h * 0.2
            canvas.create_rectangle(wx0, wy0, wx0 + ww, wy0 + wh, fill="#f1c76f", outline="#6f5137", width=1, tags="atmo")
            canvas.create_line(wx0 + (ww * 0.5), wy0, wx0 + (ww * 0.5), wy0 + wh, fill="#6f5137", width=1, tags="scene")
            canvas.create_line(wx0, wy0 + (wh * 0.5), wx0 + ww, wy0 + (wh * 0.5), fill="#6f5137", width=1, tags="scene")
        fence_wave = math.sin((t * 0.5) + 0.5) * (width * 0.002)
        canvas.create_line(house_base_x - house_w * 0.8, house_base_y, house_base_x - house_w * 0.18, house_base_y - height * 0.005 + fence_wave, fill="#4a3426", width=max(2, int(width * 0.002)), tags="scene")
        canvas.create_line(house_base_x + house_w * 0.18, house_base_y - height * 0.005, house_base_x + house_w * 0.82, house_base_y + fence_wave, fill="#4a3426", width=max(2, int(width * 0.002)), tags="scene")
        for idx in range(6):
            px = house_base_x - house_w * 0.76 + (idx * house_w * 0.13)
            canvas.create_line(px, house_base_y + height * 0.012, px, house_base_y - height * 0.03, fill="#4a3426", width=1, tags="scene")
        canvas.create_polygon([(house_base_x - house_w * 0.14, house_base_y - house_h), (house_base_x + house_w * 0.04, house_base_y - house_h - height * 0.032), (house_base_x + house_w * 0.16, house_base_y - house_h)], fill="#60473c", outline="#8a6659", width=1, tags="scene")
        window_phase = float(state.get("window_phase", 0.0) or 0.0)
        window_glow = 0.45 + (0.35 * math.sin((t * 0.9) + window_phase + (gpu_util * 0.9)))
        window_fill = mix_color((108, 86, 34), (248, 214, 108), window_glow)
        canvas.create_rectangle(house_base_x - house_w * 0.05, house_base_y - house_h * 0.48, house_base_x + house_w * 0.05, house_base_y - house_h * 0.3, fill=window_fill, outline="", tags="atmo")
        lantern_x = house_base_x - house_w * 0.22
        lantern_y = house_base_y - house_h * 0.54
        lantern_glow = 0.55 + (0.35 * math.sin((t * 1.4) + float(state.get("lantern_phase", 0.0) or 0.0)))
        for idx, scale in enumerate((2.2, 1.4)):
            glow_r = width * 0.008 * scale
            canvas.create_oval(lantern_x - glow_r, lantern_y - glow_r, lantern_x + glow_r, lantern_y + glow_r, outline=mix_color((95, 76, 32), (245, 204, 110), lantern_glow - idx * 0.18), width=1, tags="atmo")
        canvas.create_rectangle(lantern_x - width * 0.004, lantern_y - height * 0.009, lantern_x + width * 0.004, lantern_y + height * 0.004, fill="#f0c66d", outline="#5f4a2d", width=1, tags="scene")

        path_points = [(house_base_x - house_w * 0.08, house_base_y), (house_base_x - house_w * 0.02, house_base_y + height * 0.03), (width * 0.6, height * 0.86), (width * 0.55, height * 0.97)]
        meadow_points = [(0, height), (0, height * 0.9), (width * 0.14, height * 0.84), (width * 0.28, height * 0.88), (width * 0.43, height * 0.82), (width * 0.6, height * 0.87), (width * 0.8, height * 0.8), (width, height * 0.84), (width, height)]
        canvas.create_line(path_points, fill="#5a4838", width=max(8, int(width * 0.009)), smooth=True, splinesteps=18, tags="scene")
        canvas.create_polygon(meadow_points, fill="#14251c", outline="#254635", smooth=True, splinesteps=24, tags="scene")
        for band in state.get("mist_bands", []):
            y = height * float(band.get("y", 0.75) or 0.75)
            thickness = height * float(band.get("thickness", 0.05) or 0.05)
            drift = math.sin((t * float(band.get("speed", 0.002) or 0.002) * 40.0) + float(band.get("phase", 0.0) or 0.0)) * width * 0.03
            alpha = float(band.get("alpha", 0.5) or 0.5)
            tone = mix_color((22, 34, 46), (82, 118, 138), alpha)
            canvas.create_oval(-width * 0.08 + drift, y - thickness, width * 1.08 + drift, y + thickness, outline=tone, width=1, tags="atmo")

        porch_person_x = house_base_x - house_w * 0.18
        porch_person_y = house_base_y - height * 0.018
        chair_w = width * 0.028
        chair_h = height * 0.028
        rock = math.sin((t * 1.1) + 0.4) * width * 0.004
        canvas.create_arc(porch_person_x - chair_w * 0.7 + rock, porch_person_y + chair_h * 0.18, porch_person_x + chair_w * 0.55 + rock, porch_person_y + chair_h * 1.2, start=205, extent=120, style="arc", outline="#7c5b44", width=2, tags="scene")
        canvas.create_line(porch_person_x - chair_w * 0.5 + rock, porch_person_y - chair_h * 0.55, porch_person_x - chair_w * 0.68 + rock, porch_person_y + chair_h * 0.38, fill="#7c5b44", width=2, tags="scene")
        canvas.create_line(porch_person_x - chair_w * 0.5 + rock, porch_person_y - chair_h * 0.55, porch_person_x + chair_w * 0.2 + rock, porch_person_y - chair_h * 0.55, fill="#7c5b44", width=2, tags="scene")
        canvas.create_line(porch_person_x + chair_w * 0.1 + rock, porch_person_y - chair_h * 0.45, porch_person_x + chair_w * 0.26 + rock, porch_person_y + chair_h * 0.18, fill="#7c5b44", width=2, tags="scene")
        canvas.create_line(porch_person_x - chair_w * 0.4 + rock, porch_person_y, porch_person_x + chair_w * 0.02 + rock, porch_person_y + chair_h * 0.24, fill="#e7d2a5", width=3, tags="scene")
        canvas.create_line(porch_person_x - chair_w * 0.1 + rock, porch_person_y - chair_h * 0.34, porch_person_x + chair_w * 0.22 + rock, porch_person_y - chair_h * 0.08, fill="#5e4738", width=3, tags="scene")
        canvas.create_oval(porch_person_x - chair_w * 0.22 + rock, porch_person_y - chair_h * 0.68, porch_person_x + chair_w * 0.02 + rock, porch_person_y - chair_h * 0.44, fill="#caa57d", outline="#6d5240", width=1, tags="scene")
        canvas.create_line(porch_person_x + chair_w * 0.04 + rock, porch_person_y - chair_h * 0.5, porch_person_x + chair_w * 0.18 + rock, porch_person_y - chair_h * 0.55, fill="#caa57d", width=2, tags="scene")
        canvas.create_line(porch_person_x + chair_w * 0.18 + rock, porch_person_y - chair_h * 0.55, porch_person_x + chair_w * 0.24 + rock, porch_person_y - chair_h * 0.58, fill="#c25a31", width=2, tags="scene")
        canvas.create_oval(porch_person_x + chair_w * 0.23 + rock, porch_person_y - chair_h * 0.6, porch_person_x + chair_w * 0.27 + rock, porch_person_y - chair_h * 0.56, fill="#ff7d3b", outline="", tags="atmo")
        for idx in range(3):
            smoke_y = porch_person_y - chair_h * (0.68 + idx * 0.36)
            smoke_x = porch_person_x + chair_w * 0.26 + rock + math.sin((t * 0.9) + idx) * width * 0.004
            smoke_r = width * (0.004 + idx * 0.0016)
            canvas.create_oval(smoke_x - smoke_r, smoke_y - smoke_r, smoke_x + smoke_r, smoke_y + smoke_r, outline="#98a6b5", width=1, tags="atmo")
        canvas.create_line(porch_person_x + chair_w * 0.06 + rock, porch_person_y - chair_h * 0.14, porch_person_x + chair_w * 0.24 + rock, porch_person_y + chair_h * 0.06, fill="#d7c0a0", width=2, tags="scene")
        canvas.create_rectangle(porch_person_x + chair_w * 0.22 + rock, porch_person_y + chair_h * 0.02, porch_person_x + chair_w * 0.34 + rock, porch_person_y + chair_h * 0.18, fill="#8f6336", outline="#d9bf77", width=1, tags="scene")

        standing_x = width * 0.625
        standing_y = height * 0.9
        beam_sway = math.sin((t * 0.7) + 1.2) * width * 0.02
        canvas.create_line(standing_x, standing_y - height * 0.042, standing_x, standing_y - height * 0.01, fill="#d9d9de", width=3, tags="scene")
        canvas.create_line(standing_x, standing_y - height * 0.028, standing_x - width * 0.011, standing_y - height * 0.008, fill="#d9d9de", width=2, tags="scene")
        canvas.create_line(standing_x, standing_y - height * 0.028, standing_x + width * 0.015, standing_y - height * 0.02, fill="#d9d9de", width=2, tags="scene")
        canvas.create_line(standing_x, standing_y - height * 0.01, standing_x - width * 0.01, standing_y + height * 0.024, fill="#455064", width=2, tags="scene")
        canvas.create_line(standing_x, standing_y - height * 0.01, standing_x + width * 0.012, standing_y + height * 0.026, fill="#455064", width=2, tags="scene")
        canvas.create_oval(standing_x - width * 0.007, standing_y - height * 0.056, standing_x + width * 0.007, standing_y - height * 0.042, fill="#d1b18d", outline="#6d5240", width=1, tags="scene")
        flashlight_hand_x = standing_x + width * 0.015
        flashlight_hand_y = standing_y - height * 0.02
        beam_tip_x = width * 0.51 + beam_sway
        beam_tip_y = height * 0.84
        for idx, ratio in enumerate((1.0, 0.72, 0.48)):
            canvas.create_polygon([(flashlight_hand_x, flashlight_hand_y - height * 0.008 * ratio), (flashlight_hand_x, flashlight_hand_y + height * 0.008 * ratio), (beam_tip_x, beam_tip_y + height * 0.045 * ratio), (beam_tip_x + width * 0.055 * ratio, beam_tip_y - height * 0.022 * ratio)], fill=mix_color((37, 65, 84), (110, 154, 174), 0.18 + idx * 0.12), outline="", tags="atmo")
        canvas.create_rectangle(flashlight_hand_x - width * 0.004, flashlight_hand_y - height * 0.006, flashlight_hand_x + width * 0.006, flashlight_hand_y + height * 0.002, fill="#596b79", outline="#a4b3bb", width=1, tags="scene")
        canvas.create_oval(beam_tip_x + width * 0.02, beam_tip_y - height * 0.01, beam_tip_x + width * 0.08, beam_tip_y + height * 0.03, outline="#c5ecff", width=1, tags="atmo")

        pond_poly = [(width * 0.315, height * 0.812), (width * 0.42, height * 0.778), (width * 0.56, height * 0.79), (width * 0.635, height * 0.842), (width * 0.59, height * 0.904), (width * 0.43, height * 0.918), (width * 0.302, height * 0.882)]
        canvas.create_polygon(pond_poly, fill="#0c2230", outline="#1f5163", smooth=True, splinesteps=24, tags="scene")
        draw_reflection_lines(moon_x + width * 0.27, pond_center_y - height * 0.01, pond_rx * 0.5, height * 0.06, "#7aa0c5", density=7)
        draw_reflection_lines(cave_x + width * 0.05, pond_center_y - height * 0.015, pond_rx * 0.18, height * 0.03, "#36b7ba", density=5)
        if dragon_reflection_strength > 0.0:
            draw_reflection_lines(dragon_reflection_x, pond_center_y - height * 0.03, pond_rx * 0.38, height * 0.045, "#ff8a42", density=6)
        for idx in range(8):
            shimmer_phase = (t * 0.5) + (idx * 0.66) + (growth_memory * 18.0)
            line_y = height * (0.793 + (idx * 0.014))
            left = width * (0.355 + (0.01 * math.sin(shimmer_phase)))
            right = width * (0.615 + (0.013 * math.sin(shimmer_phase + 0.75)))
            tone = 72 + int(46 * (0.5 + (0.5 * math.sin(shimmer_phase))))
            canvas.create_line(left, line_y, right, line_y, fill=f"#2c{tone:02x}{min(220, tone + 38):02x}", width=1, tags="atmo")
        for reed_x in (0.32, 0.34, 0.36, 0.6, 0.62, 0.64):
            base_x = width * reed_x
            base_y = height * (0.84 if reed_x < 0.5 else 0.855)
            sway = math.sin((t * 0.55) + reed_x * 9.0) * width * 0.004
            canvas.create_line(base_x, base_y, base_x + sway, base_y - height * 0.04, fill="#5f8f5a", width=1, tags="scene")
            canvas.create_oval(base_x + sway - width * 0.002, base_y - height * 0.045, base_x + sway + width * 0.002, base_y - height * 0.036, fill="#9a7b46", outline="", tags="scene")
        for lily_x, lily_y in ((0.43, 0.84), (0.5, 0.865), (0.55, 0.825)):
            px = width * lily_x
            py = height * lily_y
            r = width * 0.01
            canvas.create_arc(px - r, py - r, px + r, py + r, start=24, extent=312, style="pieslice", fill="#3f7d53", outline="#79b18a", width=1, tags="scene")

        for fish in state.get("fish", []):
            raw_x = fish["x"] + (math.sin((t * fish["speed"]) + fish["phase"]) * 0.05)
            raw_y = fish["y"] + (math.cos((t * (fish["speed"] * 1.5)) + fish["phase"]) * (0.008 + (float(fish["lane"]) * 0.008)))
            norm_x = (raw_x - (pond_center_x / width)) / (pond_rx / width)
            norm_y = (raw_y - (pond_center_y / height)) / (pond_ry / height)
            dist = math.sqrt((norm_x * norm_x) + (norm_y * norm_y))
            if dist > 0.96:
                scale = 0.96 / max(dist, 1e-6)
                norm_x *= scale
                norm_y *= scale
            px = ((pond_center_x / width) + (norm_x * (pond_rx / width))) * width
            py = ((pond_center_y / height) + (norm_y * (pond_ry / height))) * height
            body_w = width * (0.0055 + (float(fish["depth"]) * 0.0026))
            body_h = height * (0.0038 + (float(fish["depth"]) * 0.0014))
            fish_fill = mix_color((186, 106, 54), (244, 160, 92), 0.55 + (0.25 * math.sin(t + float(fish["phase"]))))
            canvas.create_polygon([(px - body_w, py), (px - body_w * 0.3, py - body_h), (px + body_w * 0.7, py - body_h * 0.55), (px + body_w, py), (px + body_w * 0.7, py + body_h * 0.55), (px - body_w * 0.3, py + body_h)], fill=fish_fill, outline="#7a3f21", width=1, smooth=True, splinesteps=12, tags="scene")
            heading = -1.0 if math.sin((t * float(fish["speed"]) * 2.0) + float(fish["phase"])) < 0 else 1.0
            canvas.create_polygon([(px - heading * body_w, py), (px - heading * body_w * 1.8, py - body_h * 0.95), (px - heading * body_w * 1.8, py + body_h * 0.95)], fill=fish_fill, outline="#7a3f21", width=1, tags="scene")
            if math.sin((t * float(fish["speed"]) * 2.5) + float(fish["phase"])) > 0.92:
                ripple_r = width * 0.006
                canvas.create_oval(px - ripple_r, py - ripple_r, px + ripple_r, py + ripple_r, outline="#4f7ea0", width=1, tags="atmo")

        for duck in state.get("ducks", []):
            lane = float(duck.get("lane", 0.5) or 0.5)
            heading = float(duck.get("heading", 1.0) or 1.0)
            duck_scale = float(duck.get("size", 1.0) or 1.0)
            duck_t = (float(duck.get("phase", 0.0) or 0.0) + (t * float(duck.get("speed", 0.09) or 0.09))) % 1.0
            pond_duck_x = width * (0.365 + (0.165 * lane))
            pond_duck_y = height * (0.818 + (0.026 * lane))
            if duck_t < 0.24:
                progress = duck_t / 0.24
                x = width * (1.14 - (0.74 * progress)) if heading < 0 else width * (-0.14 + (0.74 * progress))
                y = height * (0.26 + (lane * 0.08) + ((1.0 - progress) ** 1.4) * 0.19)
                wing_lift = math.sin((t * 11.0) + float(duck.get("wing_phase", 0.0) or 0.0)) * 0.98
                if progress > 0.88:
                    draw_splash(pond_duck_x, pond_duck_y + height * 0.012, 0.85 * duck_scale, (progress - 0.88) / 0.12)
                draw_duck(x, y, duck_scale, wing_lift, heading)
            elif duck_t < 0.66:
                progress = (duck_t - 0.24) / 0.42
                bob = math.sin((t * (2.2 + float(duck.get("pond_jitter", 1.0) or 1.0))) + float(duck.get("wing_phase", 0.0) or 0.0))
                x = pond_duck_x + math.sin((t * float(duck.get("speed", 0.09) or 0.09) * 4.2) + float(duck.get("phase", 0.0) or 0.0)) * width * 0.012
                y = pond_duck_y + bob * height * 0.0038
                wing_lift = 0.08 * math.sin((t * 1.4) + float(duck.get("wing_phase", 0.0) or 0.0))
                draw_reflection_lines(x, y + height * 0.012, width * 0.028 * duck_scale, height * 0.004, "#88abc0", density=3)
                if progress < 0.08 or progress > 0.9:
                    draw_splash(x, y + height * 0.01, 0.54 * duck_scale, 0.55)
                draw_duck(x, y, duck_scale * 0.98, wing_lift, heading, on_water=True)
            else:
                progress = (duck_t - 0.66) / 0.34
                run = min(1.0, progress / 0.46)
                lift = max(0.0, progress - 0.18) / 0.82
                x = pond_duck_x + ((width * 0.22) * run * heading)
                y = pond_duck_y - (height * 0.012 * run) - (height * 0.2 * (lift ** 1.35))
                wing_lift = math.sin((t * 12.5) + float(duck.get("wing_phase", 0.0) or 0.0)) * (0.55 + (0.65 * lift))
                if progress < 0.5:
                    step_phase = ((progress / 0.5) * 5.0) % 1.0
                    draw_splash(x - (width * 0.014 * heading), pond_duck_y + height * 0.012, 0.65 * duck_scale, 0.35 + (0.65 * math.sin(step_phase * math.pi)))
                draw_duck(x, y, duck_scale, wing_lift, heading, running=progress < 0.28)

        for idx, rel_x in enumerate((0.06, 0.17, 0.28, 0.83, 0.9)):
            px = width * rel_x
            base_y = height * (0.78 + ((idx % 3) * 0.03))
            pine_h = height * (0.08 + ((idx % 2) * 0.025))
            trunk_w = max(2, int(width * 0.003))
            canvas.create_line(px, base_y, px, base_y + (pine_h * 0.22), fill="#231a14", width=trunk_w, tags="scene")
            canvas.create_polygon([(px, base_y - pine_h), (px - pine_h * 0.22, base_y - pine_h * 0.42), (px - pine_h * 0.15, base_y - pine_h * 0.42), (px - pine_h * 0.28, base_y), (px + pine_h * 0.28, base_y), (px + pine_h * 0.15, base_y - pine_h * 0.42), (px + pine_h * 0.22, base_y - pine_h * 0.42)], fill="#0d2019", outline="#1d3c31", smooth=True, splinesteps=12, tags="scene")

        grass_line = [(0, height * 0.88), (width * 0.12, height * 0.84), (width * 0.27, height * 0.885), (width * 0.43, height * 0.83), (width * 0.56, height * 0.875), (width * 0.71, height * 0.82), (width * 0.86, height * 0.86), (width, height * 0.84)]
        canvas.create_line(grass_line, fill="#31523d", width=max(3, int(width * 0.0025)), smooth=True, splinesteps=24, tags="scene")

        firefly_count = 10 + int(round(growth_memory * 140.0)) + int(round(curiosity * 4.0))
        for firefly in state.get("fireflies", [])[:firefly_count]:
            fx = firefly["x"] + (math.sin((t * firefly["speed"]) + firefly["phase"]) * firefly["drift_x"])
            fy = firefly["y"] + (math.cos((t * (firefly["speed"] * 0.8)) + firefly["phase"]) * firefly["drift_y"])
            px = fx * width
            py = fy * height
            pulse = 0.45 + (0.55 * math.sin((t * 2.2) + firefly["phase"]))
            radius = firefly["radius"] * (0.7 + (0.45 * pulse))
            glow_radius = radius * 3.2
            glow = mix_color((76, 108, 42), (186, 248, 122), pulse)
            core = mix_color((164, 144, 70), (255, 248, 186), pulse)
            canvas.create_oval(px - glow_radius, py - glow_radius, px + glow_radius, py + glow_radius, outline=glow, width=1, tags="atmo")
            canvas.create_oval(px - radius, py - radius, px + radius, py + radius, fill=core, outline="", tags="scene")

    def _ensure_therapeutic_bilateral_state(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        if self._therapeutic_scene_state and self._therapeutic_scene_dimensions == (width, height):
            return
        rng = random.Random(1847)
        self._therapeutic_scene_dimensions = (width, height)
        self._therapeutic_scene_started_ts = time.monotonic()
        self._therapeutic_scene_state = {
            "stars": [
                {
                    "x": rng.uniform(0.05, 0.95),
                    "y": rng.uniform(0.06, 0.92),
                    "size": rng.uniform(0.8, 2.2),
                    "phase": rng.uniform(0.0, math.tau),
                    "speed": rng.uniform(0.18, 0.52),
                }
                for _ in range(42)
            ],
            "ribbons": [
                {
                    "y": base_y,
                    "amp": amp,
                    "phase": rng.uniform(0.0, math.tau),
                    "speed": rng.uniform(0.12, 0.28),
                    "tone": tone,
                }
                for base_y, amp, tone in (
                    (0.28, 0.018, 0.22),
                    (0.38, 0.024, 0.34),
                    (0.62, 0.028, 0.42),
                    (0.76, 0.02, 0.5),
                )
            ],
            "grounding_cues": [
                ("soft eyes", "follow gently"),
                ("long exhale", "let the jaw unclench"),
                ("notice feet", "notice the chair"),
                ("room is here", "body is here"),
                ("drop shoulders", "slow the breath"),
            ],
        }

    def _render_therapeutic_bilateral_scene(self, canvas: Any, width: int, height: int, now: float) -> None:
        self._ensure_therapeutic_bilateral_state(width, height)
        state = self._therapeutic_scene_state
        scene_age = max(0.0, now - float(getattr(self, "_therapeutic_scene_started_ts", now) or now))
        t = scene_age * float(getattr(self, "_work_scene_time_scale", 0.28) or 0.28)
        growth_memory = float(getattr(self, "_work_growth_memory", 0.0) or 0.0)
        curiosity = float(getattr(self, "control_values", {}).get("curiosity_impulse", 0.0) or 0.0)
        gpu_util = clamp01(float(getattr(self.signals, "gpu_util", 0.0) or 0.0))
        inhale_seconds = max(1.0, float(getattr(self, "_therapeutic_inhale_seconds", 4.0) or 4.0))
        hold_seconds = max(0.0, float(getattr(self, "_therapeutic_hold_seconds", 2.0) or 2.0))
        exhale_seconds = max(1.0, float(getattr(self, "_therapeutic_exhale_seconds", 5.0) or 5.0))
        breath_seconds = max(1.0, inhale_seconds + hold_seconds + exhale_seconds)
        sweep_seconds = max(4.0, float(getattr(self, "_therapeutic_sweep_seconds", 7.5) or 7.5))
        settle_seconds = max(2.0, float(getattr(self, "_therapeutic_settle_seconds", 4.0) or 4.0))
        total_cycle = sweep_seconds + settle_seconds
        motion_gain = clamp01(float(getattr(self, "_therapeutic_motion_gain", 0.7) or 0.7))
        drift_seconds = max(45.0, float(getattr(self, "_therapeutic_drift_seconds", 180.0) or 180.0))
        drift_ratio = max(0.002, float(getattr(self, "_therapeutic_drift_ratio", 0.01) or 0.01))
        text_timeout_s = max(0.0, float(getattr(self, "_therapeutic_text_timeout_s", 60.0) or 60.0))
        grounding_enabled = bool(getattr(self, "_therapeutic_grounding_enabled", True))
        prompt_interval_s = max(8.0, float(getattr(self, "_therapeutic_prompt_interval_s", 24.0) or 24.0))

        def mix_color(start: tuple[int, int, int], end: tuple[int, int, int], ratio: float) -> str:
            ratio = clamp01(ratio)
            r = int(start[0] + ((end[0] - start[0]) * ratio))
            g = int(start[1] + ((end[1] - start[1]) * ratio))
            b = int(start[2] + ((end[2] - start[2]) * ratio))
            return f"#{r:02x}{g:02x}{b:02x}"

        def breath_state(elapsed: float) -> tuple[float, str, float]:
            elapsed = elapsed % breath_seconds
            if elapsed < inhale_seconds:
                local = ease_in_out(elapsed / max(0.001, inhale_seconds))
                return 0.14 + (0.86 * local), "inhale", local
            elapsed -= inhale_seconds
            if elapsed < hold_seconds:
                local = elapsed / max(0.001, hold_seconds) if hold_seconds > 0.0 else 1.0
                return 1.0, "hold", clamp01(local)
            elapsed -= hold_seconds
            local = ease_in_out(elapsed / max(0.001, exhale_seconds))
            return 1.0 - (0.86 * local), "exhale", local

        def ease_in_out(value: float) -> float:
            value = clamp01(value)
            return 0.5 - (0.5 * math.cos(value * math.pi))

        def clamp_anchor(px: float, py: float, margin_x: float, margin_y: float) -> tuple[float, float]:
            return (
                max(margin_x, min(width - margin_x, px)),
                max(margin_y, min(height - margin_y, py)),
            )

        canvas.delete("bg")
        canvas.delete("scene")
        canvas.delete("atmo")
        canvas.delete("text")

        drift_phase = (scene_age / max(0.001, drift_seconds)) * math.tau
        drift_x = math.sin(drift_phase) * width * drift_ratio
        drift_y = math.sin((drift_phase * 0.73) + 1.1) * height * drift_ratio * 0.62
        gradient_shift_y = drift_y * 0.32
        text_orbit_phase = (scene_age / max(36.0, prompt_interval_s * 2.0)) * math.tau

        top_color = (4, 9, 20)
        mid_color = (9, 20, 38)
        lower_color = (20, 40, 58)
        floor_color = (10, 19, 28)
        for idx in range(32):
            y0 = int(((height / 32.0) * idx) + gradient_shift_y)
            y1 = int(((height / 32.0) * (idx + 1)) + gradient_shift_y)
            ratio = idx / 31.0
            if ratio < 0.5:
                fill = mix_color(top_color, mid_color, ratio / 0.5)
            elif ratio < 0.84:
                fill = mix_color(mid_color, lower_color, (ratio - 0.5) / 0.34)
            else:
                fill = mix_color(lower_color, floor_color, (ratio - 0.84) / 0.16)
            canvas.create_rectangle(0, y0, width, y1 + 1, fill=fill, outline="", tags="bg")

        ambient_strength = clamp01(0.2 + (growth_memory * 12.0) + (curiosity * 0.4) + (gpu_util * 0.18))
        horizon_y = height * 0.82
        canvas.create_polygon(
            [
                (0, height),
                (0, horizon_y + (drift_y * 0.14)),
                ((width * 0.18) + (drift_x * 0.24), (height * 0.76) + (drift_y * 0.2)),
                ((width * 0.38) + (drift_x * 0.12), (height * 0.8) + (drift_y * 0.16)),
                ((width * 0.62) - (drift_x * 0.1), (height * 0.75) + (drift_y * 0.22)),
                ((width * 0.86) - (drift_x * 0.2), (height * 0.79) + (drift_y * 0.18)),
                (width, (height * 0.77) + (drift_y * 0.12)),
                (width, height),
            ],
            fill="#081018",
            outline="",
            smooth=True,
            splinesteps=18,
            tags="scene",
        )

        for ribbon in state.get("ribbons", []):
            points: list[float] = []
            for idx in range(18):
                ratio = idx / 17.0
                px = (ratio * width) + (drift_x * 0.55)
                py = height * float(ribbon.get("y", 0.5) or 0.5)
                py += math.sin((ratio * math.tau * 1.3) + (t * float(ribbon.get("speed", 0.2) or 0.2)) + float(ribbon.get("phase", 0.0) or 0.0)) * height * float(ribbon.get("amp", 0.02) or 0.02)
                py += drift_y * 0.45
                points.extend((px, py))
            tone = float(ribbon.get("tone", 0.3) or 0.3)
            fill = mix_color((18, 58, 78), (84, 138, 152), tone + ambient_strength * 0.2)
            canvas.create_line(points, fill=fill, width=max(2, int(height * 0.0045)), smooth=True, splinesteps=18, tags="atmo")

        for star in state.get("stars", []):
            star_t = t * float(star.get("speed", 0.3) or 0.3)
            px = width * float(star.get("x", 0.5) or 0.5)
            py = height * float(star.get("y", 0.5) or 0.5)
            px += drift_x * 0.68
            py += drift_y * 0.52
            px += math.sin(star_t + float(star.get("phase", 0.0) or 0.0)) * width * 0.0026
            py += math.cos((star_t * 0.8) + float(star.get("phase", 0.0) or 0.0)) * height * 0.0022
            pulse = 0.35 + (0.65 * math.sin((t * float(star.get("speed", 0.3) or 0.3)) + float(star.get("phase", 0.0) or 0.0)))
            radius = float(star.get("size", 1.2) or 1.2) * (0.65 + (0.28 * pulse))
            core = mix_color((84, 122, 148), (210, 232, 241), pulse)
            canvas.create_oval(px - radius, py - radius, px + radius, py + radius, fill=core, outline="", tags="scene")
            if pulse > 0.82:
                glow = radius * 4.2
                canvas.create_line(px - glow, py, px + glow, py, fill="#86b9c6", width=1, tags="atmo")

        breath_elapsed = scene_age % breath_seconds
        breath_progress = breath_elapsed / max(0.001, breath_seconds)
        breath_strength, breath_label, breath_phase_progress = breath_state(breath_elapsed)
        center_x = (width * 0.5) + drift_x
        center_y = (height * 0.56) + drift_y
        base_radius = min(width, height) * 0.09
        ring_radius = base_radius * (0.82 + (0.34 * breath_strength))
        ring_thickness = max(2.0, min(width, height) * 0.003)
        glow_radius = ring_radius * (1.45 + ambient_strength * 0.35)
        canvas.create_oval(center_x - glow_radius, center_y - glow_radius, center_x + glow_radius, center_y + glow_radius, outline="#315f6a", width=1, tags="atmo")
        canvas.create_oval(center_x - ring_radius, center_y - ring_radius, center_x + ring_radius, center_y + ring_radius, outline="#8ed6d7", width=ring_thickness, tags="scene")
        inner_radius = ring_radius * 0.56
        canvas.create_oval(center_x - inner_radius, center_y - inner_radius, center_x + inner_radius, center_y + inner_radius, fill="#0d1c27", outline="#2c5562", width=1, tags="scene")

        cycle_index = int(scene_age / max(0.001, total_cycle))
        cycle_elapsed = scene_age % total_cycle
        prompt_elapsed = scene_age % prompt_interval_s
        orb_y = center_y
        sweep_amp = width * (0.28 + (0.05 * motion_gain))
        if cycle_elapsed < sweep_seconds:
            sweep_progress = cycle_elapsed / max(0.001, sweep_seconds)
            sweep_wave = math.sin((sweep_progress * math.pi) - (math.pi * 0.5))
            direction = 1.0 if (cycle_index % 2) == 0 else -1.0
            orb_x = center_x + (sweep_amp * sweep_wave * direction)
            motion_label = "sweep"
            direction_label = "left_to_right" if direction > 0.0 else "right_to_left"
        else:
            settle_progress = (cycle_elapsed - sweep_seconds) / max(0.001, settle_seconds)
            settle_wave = 1.0 - ease_in_out(settle_progress)
            last_edge = 1.0 if (cycle_index % 2) == 0 else -1.0
            orb_x = center_x + (sweep_amp * last_edge * settle_wave)
            motion_label = "settle"
            direction_label = "right_edge" if last_edge > 0.0 else "left_edge"
        orb_y += math.sin((t * 0.8) + (breath_progress * math.tau)) * height * 0.008 * motion_gain

        trail_color = mix_color((38, 90, 102), (116, 214, 212), 0.5 + ambient_strength * 0.28)
        for idx in range(7):
            trail_ratio = idx / 6.0
            trail_decay = 1.0 - trail_ratio
            trail_offset = sweep_amp * 0.18 * trail_ratio * (1.0 if motion_label == "sweep" else 0.0)
            trail_x = orb_x - trail_offset if (cycle_index % 2) == 0 else orb_x + trail_offset
            trail_y = orb_y + math.sin((t * 0.8) + (trail_ratio * 0.4)) * height * 0.003
            trail_r = max(2.0, ring_radius * (0.1 + trail_decay * 0.08))
            outline = mix_color((24, 58, 66), (92, 178, 186), trail_decay * 0.7)
            canvas.create_oval(trail_x - trail_r, trail_y - trail_r, trail_x + trail_r, trail_y + trail_r, outline=outline, width=1, tags="atmo")
        orb_r = ring_radius * 0.12
        canvas.create_oval(orb_x - orb_r * 2.2, orb_y - orb_r * 2.2, orb_x + orb_r * 2.2, orb_y + orb_r * 2.2, outline=trail_color, width=1, tags="atmo")
        canvas.create_oval(orb_x - orb_r, orb_y - orb_r, orb_x + orb_r, orb_y + orb_r, fill="#d6fbf7", outline="#86ddd7", width=1, tags="scene")

        left_anchor_x = center_x - sweep_amp
        right_anchor_x = center_x + sweep_amp
        anchor_r = ring_radius * 0.09
        for anchor_x in (left_anchor_x, right_anchor_x):
            canvas.create_oval(anchor_x - anchor_r, center_y - anchor_r, anchor_x + anchor_r, center_y + anchor_r, outline="#315966", width=1, tags="atmo")

        cues = state.get("grounding_cues", [])
        cue_primary = ""
        cue_secondary = ""
        cue_visible = False
        cue_anchor_x = center_x
        cue_anchor_y = (height * 0.79) + (drift_y * 0.34)
        text_enabled = text_timeout_s <= 0.0 or scene_age < text_timeout_s
        if text_enabled and grounding_enabled and cues:
            cue_index = int(scene_age / prompt_interval_s) % len(cues)
            cue_primary, cue_secondary = cues[cue_index]
            cue_anchor_x = center_x + (math.sin(text_orbit_phase + (cue_index * 1.17)) * width * 0.072)
            cue_anchor_y = (height * 0.79) + (math.cos((text_orbit_phase * 0.81) + (cue_index * 0.91)) * height * 0.04) + (drift_y * 0.34)
            cue_anchor_x, cue_anchor_y = clamp_anchor(cue_anchor_x, cue_anchor_y, width * 0.12, height * 0.12)
            cue_visible = prompt_elapsed < min(10.0, prompt_interval_s * 0.42)
            if cue_visible:
                canvas.create_text(
                    cue_anchor_x,
                    cue_anchor_y - (height * 0.022),
                    text=cue_primary,
                    fill="#c6dfdc",
                    font=("Helvetica", max(16, int(height * 0.026)), "bold"),
                    tags="text",
                )
                canvas.create_text(
                    cue_anchor_x,
                    cue_anchor_y + (height * 0.02),
                    text=cue_secondary,
                    fill="#789da0",
                    font=("Helvetica", max(12, int(height * 0.019))),
                    tags="text",
                )

        breath_caption = "inhale 4  |  hold 2  |  exhale 5"
        breath_anchor_x = center_x + (math.sin(text_orbit_phase + 2.1) * width * 0.058)
        breath_anchor_y = (height * 0.195) + (math.cos((text_orbit_phase * 0.77) + 1.4) * height * 0.03) + (drift_y * 0.24)
        breath_anchor_x, breath_anchor_y = clamp_anchor(breath_anchor_x, breath_anchor_y, width * 0.12, height * 0.1)
        breath_label_visible = text_enabled
        breath_caption_visible = text_enabled and breath_progress < 0.55
        if breath_label_visible:
            canvas.create_text(
                breath_anchor_x,
                breath_anchor_y,
                text=breath_label.upper(),
                fill="#88b4b6",
                font=("Helvetica", max(12, int(height * 0.018)), "bold"),
                tags="text",
            )
        if breath_caption_visible:
            canvas.create_text(
                breath_anchor_x,
                breath_anchor_y + (height * 0.028),
                text=breath_caption,
                fill="#597e81",
                font=("Helvetica", max(11, int(height * 0.016))),
                tags="text",
            )

        phase_text = "bilateral settling" if motion_label == "settle" else f"bilateral sweep {direction_label.replace('_', ' ')}"
        footer = phase_text if not grounding_enabled else f"{phase_text}  |  regulation only"
        footer_anchor_x = center_x + (math.sin(text_orbit_phase + 4.2) * width * 0.082)
        footer_anchor_y = (height * 0.93) + (math.cos((text_orbit_phase * 0.63) + 0.5) * height * 0.016) + (drift_y * 0.16)
        footer_anchor_x, footer_anchor_y = clamp_anchor(footer_anchor_x, footer_anchor_y, width * 0.14, height * 0.06)
        footer_visible = text_enabled and cycle_elapsed < min(3.2, total_cycle * 0.28)
        if footer_visible:
            canvas.create_text(
                footer_anchor_x,
                footer_anchor_y,
                text=footer,
                fill="#3f5e60",
                font=("Helvetica", max(10, int(height * 0.015))),
                tags="text",
            )
        state["current_cue"] = cue_primary
        state["current_phase"] = motion_label
        state["current_direction"] = direction_label
        state["current_breath"] = breath_label
        state["breath_elapsed_seconds"] = round(float(breath_elapsed), 3)
        state["breath_phase_progress"] = round(float(breath_phase_progress), 6)
        state["ring_radius_px"] = round(float(ring_radius), 3)
        state["text_enabled"] = text_enabled
        state["cue_text_visible"] = cue_visible
        state["footer_text_visible"] = footer_visible
        state["breath_label_visible"] = breath_label_visible
        state["breath_caption_visible"] = breath_caption_visible
        state["drift_x_px"] = round(float(drift_x), 3)
        state["drift_y_px"] = round(float(drift_y), 3)

    def _sync_gpu_particle_buffers(self) -> None:
        if not self.gpu_mode:
            return
        if self._ssbo_pos is None or self._ssbo_vel is None or np is None:
            return
        self._ssbo_pos.write(self.positions.tobytes())
        self._ssbo_vel.write(self.velocities.tobytes())

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
        collapse_vis = clamp01(
            float(
                getattr(
                    self,
                    "collapse_visual_intensity",
                    getattr(getattr(self, "mirror_state", MirrorState()), "collapse_risk", 0.0),
                )
                or 0.0
            )
        )
        repair_vis = clamp01(
            float(
                getattr(
                    self,
                    "repair_visual_intensity",
                    getattr(getattr(self, "mirror_state", MirrorState()), "repair_progress", 0.0),
                )
                or 0.0
            )
        )
        self.effective_exposure = max(0.2, min(1.95, self.effective_exposure * (1.0 - (0.16 * collapse_vis) + (0.08 * repair_vis))))
        self.effective_saturation = max(
            0.35,
            min(2.5, self.effective_saturation - (0.28 * collapse_vis) + (0.16 * repair_vis)),
        )
        self.temporal_alpha = max(0.55, min(0.985, self.temporal_alpha - (0.08 * collapse_vis) + (0.06 * repair_vis)))

        density_target = int(self.particles_target * self.control_values["density_boost"])
        density_target = max(self.min_agent_count, min(self.agent_count, density_target))
        self.particles_visible = int((self.particles_visible * 0.65) + (density_target * 0.35))
        self.particles_visible = max(self.min_agent_count, min(self.agent_count, self.particles_visible))

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
        self.shader_params["turbulence"] = clamp01(self.shader_params["turbulence"] + (0.22 * collapse_vis) - (0.08 * repair_vis))
        self.shader_params["velocity"] = clamp01(
            self.shader_params.get("velocity", 0.0) + (0.08 * collapse_vis) - (0.14 * repair_vis)
        )
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

    def _palette_mode_index(self) -> int:
        return {"dusk": 0, "aurora": 1, "roseglass": 2, "ember": 3, "mono": 4}.get(self.palette_mode, 0)

    def set_palette_mode(self, mode: str) -> bool:
        normalized = str(mode or "").strip().lower()
        if normalized not in {"dusk", "aurora", "roseglass", "ember", "mono"}:
            return False
        self.palette_mode = normalized
        return True

    def set_load_shed(self, *, active: bool, reason: str = "") -> None:
        target_active = bool(active)
        if target_active == self.load_shed_active and (not target_active or reason == self.shed_reason):
            return
        self.load_shed_active = target_active
        self.shed_reason = str(reason or "")
        if target_active:
            self.particles_target = max(self.min_agent_count, min(self.agent_count, int(self._particles_target_base * 0.62)))
            self.vol_steps = max(20, min(self._vol_steps_base, int(self._vol_steps_base * 0.7)))
        else:
            self.particles_target = int(self._particles_target_base)
            self.vol_steps = int(self._vol_steps_base)
        self.log.log(
            "load_shed_state",
            active=self.load_shed_active,
            reason=self.shed_reason,
            particles_target=self.particles_target,
            vol_steps=self.vol_steps,
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
                uniform int palette_mode;
                uniform vec3 white_balance;
                uniform float layer_weight_rd;
                uniform float layer_weight_volume;
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
                vec3 _mix3(vec3 a, vec3 b, float t) { return mix(a, b, clamp(t, 0.0, 1.0)); }
                vec3 palette_sample(float t, int mode) {
                    t = clamp(t, 0.0, 1.0);
                    t = smoothstep(0.12, 0.82, t);
                    vec3 navy = vec3(0.047, 0.063, 0.141);
                    vec3 indigo = vec3(0.153, 0.125, 0.302);
                    vec3 violet = vec3(0.302, 0.196, 0.435);
                    vec3 blush = vec3(0.780, 0.520, 0.607);
                    vec3 amber = vec3(1.000, 0.702, 0.353);
                    if (mode == 1) {
                        indigo = vec3(0.114, 0.188, 0.435);
                        violet = vec3(0.220, 0.306, 0.620);
                        blush = vec3(0.770, 0.520, 0.700);
                        amber = vec3(0.980, 0.760, 0.500);
                    } else if (mode == 2) {
                        navy = vec3(0.060, 0.070, 0.170);
                        indigo = vec3(0.270, 0.170, 0.420);
                        violet = vec3(0.490, 0.300, 0.520);
                        blush = vec3(0.830, 0.570, 0.640);
                        amber = vec3(0.990, 0.770, 0.610);
                    } else if (mode == 3) {
                        navy = vec3(0.070, 0.055, 0.110);
                        indigo = vec3(0.215, 0.130, 0.220);
                        violet = vec3(0.420, 0.235, 0.250);
                        blush = vec3(0.810, 0.470, 0.410);
                        amber = vec3(1.000, 0.720, 0.360);
                    } else if (mode == 4) {
                        float g = smoothstep(0.0, 1.0, t);
                        vec3 mono = vec3(0.15 + g * 0.75);
                        return mono * vec3(1.04, 0.98, 0.92);
                    }
                    float s1 = smoothstep(0.00, 0.27, t);
                    float s2 = smoothstep(0.27, 0.52, t);
                    float s3 = smoothstep(0.52, 0.78, t);
                    float s4 = smoothstep(0.78, 1.00, t);
                    vec3 c = _mix3(navy, indigo, s1);
                    c = _mix3(c, violet, s2);
                    c = _mix3(c, blush, s3);
                    c = _mix3(c, amber, s4);
                    return c;
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
                        float rdm = texture(rd_field, wp).y * layer_weight_rd;
                        float d = noise3(pos * (0.7 + nebula) + vec3(rdgrad * 2.5, t * 0.05));
                        d = max(0.0, d * (0.8 + rdm * 1.5) * density_boost * layer_weight_volume - 0.42);
                        d *= (0.8 + curiosity * 0.6 + audio_amp * 0.3);
                        float tone = clamp(d + rdm * 0.62 + noise3(pos * 0.11 + vec3(0.0, 0.0, t * 0.03)) * 0.08, 0.0, 1.0);
                        vec3 c = palette_sample(tone, palette_mode) * white_balance;
                        float a = clamp(d * 0.16 * layer_weight_volume, 0.0, 0.22);
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
                uniform float threshold;
                uniform float knee;
                void main() {
                    vec3 c = texture(src_tex, uv).rgb;
                    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
                    float k = max(0.0001, knee);
                    float soft = clamp((l - threshold + k) / (2.0 * k), 0.0, 1.0);
                    float contrib = max(l - threshold, 0.0) + (soft * soft * k * 0.25);
                    vec3 b = c * (contrib / max(l, 0.0001));
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
                uniform float hdr_clamp;
                uniform int debug_luma;
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
                    vec3 color = min(hdr + bloom, vec3(hdr_clamp));
                    if (debug_luma == 1) {
                        float y = clamp(dot(color, vec3(0.2126, 0.7152, 0.0722)) / max(hdr_clamp, 0.001), 0.0, 1.0);
                        vec3 heat = vec3(y, y * y, pow(y, 0.5));
                        fragColor = vec4(heat, 1.0);
                        return;
                    }
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
        if not self.allow_gpu_backend:
            if self.require_gpu:
                raise GPUUnavailableError("gpu backend disabled")
            if not self.headless and self.allow_visible_attach and self.work_mode_enabled:
                self._init_software_backend()
            return
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
                        uniform int palette_mode;
                        uniform vec3 white_balance;
                        vec3 _mix3(vec3 a, vec3 b, float t) { return mix(a, b, clamp(t, 0.0, 1.0)); }
                        vec3 palette_sample(float t, int mode) {
                            t = clamp(t, 0.0, 1.0);
                            t = smoothstep(0.12, 0.82, t);
                            vec3 navy = vec3(0.047, 0.063, 0.141);
                            vec3 indigo = vec3(0.153, 0.125, 0.302);
                            vec3 violet = vec3(0.302, 0.196, 0.435);
                            vec3 blush = vec3(0.780, 0.520, 0.607);
                            vec3 amber = vec3(1.000, 0.702, 0.353);
                            if (mode == 1) {
                                indigo = vec3(0.114, 0.188, 0.435);
                                violet = vec3(0.220, 0.306, 0.620);
                                blush = vec3(0.770, 0.520, 0.700);
                                amber = vec3(0.980, 0.760, 0.500);
                            } else if (mode == 2) {
                                navy = vec3(0.060, 0.070, 0.170);
                                indigo = vec3(0.270, 0.170, 0.420);
                                violet = vec3(0.490, 0.300, 0.520);
                                blush = vec3(0.830, 0.570, 0.640);
                                amber = vec3(0.990, 0.770, 0.610);
                            } else if (mode == 3) {
                                navy = vec3(0.070, 0.055, 0.110);
                                indigo = vec3(0.215, 0.130, 0.220);
                                violet = vec3(0.420, 0.235, 0.250);
                                blush = vec3(0.810, 0.470, 0.410);
                                amber = vec3(1.000, 0.720, 0.360);
                            } else if (mode == 4) {
                                float g = smoothstep(0.0, 1.0, t);
                                vec3 mono = vec3(0.15 + g * 0.75);
                                return mono * vec3(1.04, 0.98, 0.92);
                            }
                            float s1 = smoothstep(0.00, 0.27, t);
                            float s2 = smoothstep(0.27, 0.52, t);
                            float s3 = smoothstep(0.52, 0.78, t);
                            float s4 = smoothstep(0.78, 1.00, t);
                            vec3 c = _mix3(navy, indigo, s1);
                            c = _mix3(c, violet, s2);
                            c = _mix3(c, blush, s3);
                            c = _mix3(c, amber, s4);
                            return c;
                        }
                        void main() {
                            vec2 uv = gl_PointCoord * 2.0 - 1.0;
                            float r = dot(uv, uv);
                            float alpha = smoothstep(1.0, 0.2, r) * luminosity;
                            vec3 color = palette_sample(clamp(warmth * 0.85 + luminosity * 0.45, 0.0, 1.0), palette_mode);
                            color *= white_balance;
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

    def _mark_software_window_closed(self) -> None:
        self._software_window_closed = True

    def _init_software_backend(self) -> None:
        if tk is None:
            self.log.log("software_backend_unavailable", reason="tkinter unavailable")
            return
        grid_h, grid_w = self._work_grid_shape
        if grid_h <= 0 or grid_w <= 0:
            self.log.log("software_backend_unavailable", reason="work grid unavailable")
            return
        self._software_window_closed = False
        root = tk.Tk()
        root.title("DALI Work Mode Consciousness Mirror")
        root.configure(bg="#05070c")
        root.protocol("WM_DELETE_WINDOW", self._mark_software_window_closed)
        fullscreen_requested = str(os.environ.get("DALI_FISHTANK_FULLSCREEN", "0") or "0").strip() != "0"
        root.bind("<Escape>", lambda _event: (root.attributes("-fullscreen", False), root.iconify()))
        root.bind("<Control-w>", lambda _event: self._mark_software_window_closed())
        root.bind("q", lambda _event: self._mark_software_window_closed())
        screen_w = max(800, int(root.winfo_screenwidth() or 1280))
        screen_h = max(600, int(root.winfo_screenheight() or 720))
        fill_ratio = max(0.6, min(1.0, safe_float(os.environ.get("DALI_FISHTANK_WORK_WINDOW_FILL", 1.0), 1.0)))
        target_w = int(screen_w * fill_ratio)
        target_h = int(screen_h * fill_ratio)
        cell_size = max(
            1,
            min(
                12,
                int(
                    min(
                        target_w / max(1, grid_w),
                        target_h / max(1, grid_h),
                    )
                ),
            ),
        )
        window_w = grid_w * cell_size
        window_h = grid_h * cell_size
        offset_x = max(0, int((screen_w - window_w) / 2))
        offset_y = max(0, int((screen_h - window_h) / 2))
        if fullscreen_requested:
            root.geometry(f"{screen_w}x{screen_h}+0+0")
        else:
            root.geometry(f"{window_w}x{window_h}+{offset_x}+{offset_y}")
        root.minsize(max(640, window_w // 2), max(360, window_h // 2))
        try:
            root.attributes("-fullscreen", fullscreen_requested)
        except Exception:
            pass
        if not fullscreen_requested:
            try:
                root.state("zoomed")
            except Exception:
                pass
        root.lift()
        try:
            root.focus_force()
        except Exception:
            pass
        canvas = tk.Canvas(
            root,
            width=(screen_w if fullscreen_requested else window_w),
            height=(screen_h if fullscreen_requested else window_h),
            bg="#05070c",
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(fill="both", expand=True)
        self._software_window = root
        self._software_canvas = canvas
        self._software_cell_size = cell_size
        star_rng = np.random.default_rng(77 if np is not None else 77)
        if getattr(self, "_work_background_dots_enabled", True) and float(getattr(self, "_work_starfield_density", 0.2)) > 0.0:
            base_star_count = max(24, min(160, int((window_w * window_h) / 96000)))
            star_count = max(0, int(base_star_count * float(getattr(self, "_work_starfield_density", 0.2))))
            self._software_starfield = [
                (
                    float(star_rng.random()),
                    float(star_rng.random()),
                    float(star_rng.random()),
                )
                for _ in range(star_count)
            ]
        else:
            self._software_starfield = []
        self.backend = "tk-work-window"
        self.gpu_mode = False
        self.log.log(
            "software_backend_ready",
            backend=self.backend,
            width=(screen_w if fullscreen_requested else window_w),
            height=(screen_h if fullscreen_requested else window_h),
            cell_size=cell_size,
            fullscreen=fullscreen_requested,
        )

    def set_inference_active(self, active: bool) -> None:
        self.inference_active = bool(active)

    def set_runtime_context(
        self,
        *,
        lease_mode: str,
        inference_quiesced: bool,
        idle_mode_enabled: bool | None = None,
        idle_trigger_source: str | None = None,
        idle_triggered_at: str | None = None,
        display_mode_active: bool | None = None,
        idle_inhibit_enabled: bool | None = None,
        display_inhibitor_active: bool | None = None,
        inhibitor_backend: str | None = None,
    ) -> None:
        mode = str(lease_mode or "exclusive").strip().lower()
        if mode not in {"exclusive", "shared"}:
            mode = "exclusive"
        self.lease_mode = mode
        self.inference_quiesced = bool(inference_quiesced)
        if idle_mode_enabled is not None:
            self.idle_mode_enabled = bool(idle_mode_enabled)
        if idle_trigger_source is not None:
            self.idle_trigger_source = str(idle_trigger_source or "internal")
        if idle_triggered_at is not None:
            self.idle_triggered_at = str(idle_triggered_at or "")
        if display_mode_active is not None:
            self.display_mode_active = bool(display_mode_active)
        if idle_inhibit_enabled is not None:
            self.idle_inhibit_enabled = bool(idle_inhibit_enabled)
        if display_inhibitor_active is not None:
            self.display_inhibitor_active = bool(display_inhibitor_active)
        if inhibitor_backend is not None:
            self.inhibitor_backend = str(inhibitor_backend or "none")
        current_idle_mode_enabled = bool(getattr(self, "idle_mode_enabled", False))
        current_display_mode_active = bool(getattr(self, "display_mode_active", False))
        desired_headless = bool(current_idle_mode_enabled and not current_display_mode_active)
        if desired_headless:
            self._visible_attach_blocked_logged = False
        allow_visible_attach = bool(getattr(self, "allow_visible_attach", True))
        current_headless = bool(getattr(self, "headless", False))
        if not desired_headless and not allow_visible_attach:
            if current_headless and not self._visible_attach_blocked_logged:
                self.log.log(
                    "visible_attach_blocked",
                    reason="python_visible_attach_disabled",
                    backend=self.backend,
                )
                self._visible_attach_blocked_logged = True
            return
        if desired_headless != current_headless:
            self._rebuild_gpu_backend(headless=desired_headless)

    def _reset_gpu_objects(self) -> None:
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
        self.fb_w = 0
        self.fb_h = 0

    def _teardown_gpu_backend(self) -> None:
        if self._software_window is not None:
            try:
                self._software_window.destroy()
            except Exception:
                pass
        self._software_window = None
        self._software_canvas = None
        self._software_window_closed = False
        self._software_last_render_ts = 0.0
        self._software_starfield = []
        self._work_recent_pulses = []
        if self._window is not None and glfw is not None:
            try:
                glfw.destroy_window(self._window)
            except Exception:
                pass
        if glfw is not None:
            try:
                glfw.terminate()
            except Exception:
                pass
        self._reset_gpu_objects()
        self.backend = "none"
        self.gpu_mode = False

    def _rebuild_gpu_backend(self, *, headless: bool) -> None:
        self._teardown_gpu_backend()
        self.headless = bool(headless)
        if self.headless:
            self._visible_attach_blocked_logged = False
        self._init_gpu_backend()
        self.log.log("renderer_backend_rebuilt", headless=self.headless, backend=self.backend, gpu_mode=self.gpu_mode)

    def _mask_model_features(self) -> bool:
        return bool(self.inference_quiesced or self.lease_mode == "exclusive")

    def _hardware_seed_value(self, telemetry: dict[str, Any], now_ts: float) -> int:
        bucket = int(now_ts // 15)
        parts = [
            f"{safe_float(telemetry.get('gpu_temp', 0.0), 0.0):.2f}",
            f"{safe_float(telemetry.get('gpu_util', 0.0), 0.0):.4f}",
            f"{safe_float(telemetry.get('gpu_vram_used_mb', 0.0), 0.0):.2f}",
            f"{safe_float(telemetry.get('fan_gpu', telemetry.get('fan_cpu', 0.0)), 0.0):.2f}",
            f"{safe_float(telemetry.get('disk_io', 0.0), 0.0):.5f}",
            f"{safe_float(telemetry.get('network_throughput', 0.0), 0.0):.5f}",
            str(bucket),
        ]
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
        return int(digest[:12], 16)

    def _get_activity_snapshot(self, telemetry: dict[str, Any], tacti: dict[str, Any]) -> dict[str, Any]:
        snapshot = dict(getattr(self, "activity_snapshot", {}) or {})
        active_agents = tacti.get("active_agents", [])
        if not isinstance(active_agents, list):
            active_agents = []
        agent_count = int(snapshot.get("agent_count_active", len(active_agents)) or len(active_agents))
        agent_level = clamp01(
            float(snapshot.get("agent_activity_level", min(1.0, agent_count / 6.0)) or 0.0)
        )
        routing = clamp01(
            float(
                snapshot.get(
                    "routing_activity",
                    0.55 * float(tacti.get("research_depth", 0.0) or 0.0)
                    + 0.35 * float(tacti.get("token_flux", 0.0) or 0.0),
                )
                or 0.0
            )
        )
        interaction = clamp01(float(snapshot.get("interaction_activity", agent_level * 0.7) or 0.0))
        memory = clamp01(
            float(snapshot.get("memory_activity", tacti.get("memory_recall_density", 0.0) or 0.0) or 0.0)
        )
        coordination = clamp01(
            float(
                snapshot.get(
                    "coordination_density",
                    (agent_level * 0.5) + (routing * 0.25) + (interaction * 0.25),
                )
                or 0.0
            )
        )
        activity = clamp01(
            float(
                snapshot.get(
                    "activity_signal",
                    (agent_level * 0.3) + (coordination * 0.25) + (routing * 0.2) + (interaction * 0.15) + (memory * 0.1),
                )
                or 0.0
            )
        )
        summary = str(snapshot.get("semantic_activity_source_summary") or "").strip()
        if not summary:
            summary = ", ".join(
                [
                    f"agent:{agent_level:.2f}",
                    f"coordination:{coordination:.2f}",
                    f"routing:{routing:.2f}",
                    f"interaction:{interaction:.2f}",
                ]
            )
        return {
            "activity_signal": activity,
            "agent_activity_level": agent_level,
            "agent_count_active": agent_count,
            "coordination_density": coordination,
            "routing_activity": routing,
            "interaction_activity": interaction,
            "memory_activity": memory,
            "heavy_inference_suppressed": bool(snapshot.get("heavy_inference_suppressed", False)),
            "semantic_activity_source_summary": summary,
        }

    def _derive_cadence_phase(self) -> dict[str, float]:
        now = time.monotonic()
        anchor = float(getattr(self, "_dreamscape_session_anchor_mono", now) or now)
        session_s = max(0.0, now - anchor)
        self._dreamscape_session_seconds = session_s

        def _phase(period_s: float, offset: float = 0.0) -> tuple[float, float]:
            period = max(0.1, float(period_s))
            phase = ((session_s + offset) / period) % 1.0
            pulse = 0.5 + 0.5 * math.sin((phase * math.tau) - (math.pi * 0.5))
            return phase, clamp01(pulse)

        micro_phase, micro = _phase(2.8)
        cog_phase, cognition = _phase(18.0, 1.5)
        reflection_phase, reflection = _phase(240.0, 5.0)
        dream_phase, dream = _phase(120.0, 11.0)
        visual_phase, visual = _phase(28.0, 3.0)
        telluric_phase, telluric = _phase(64.0, 7.0)
        cadence = {
            "micro_pulse": micro,
            "micro_pulse_phase": micro_phase,
            "micro_pulse_period_s": 2.8,
            "cognition_cycle": cognition,
            "cognition_cycle_phase": cog_phase,
            "cognition_cycle_period_s": 18.0,
            "reflection_sweep": reflection,
            "reflection_sweep_phase": reflection_phase,
            "reflection_sweep_period_s": 240.0,
            "dream_cadence": dream,
            "dream_cycle_phase": dream_phase,
            "dream_cycle_period_s": 120.0,
            "visual_pulse": visual,
            "visual_cycle_phase": visual_phase,
            "visual_cycle_period_s": 28.0,
            "telluric_resonance": telluric,
            "telluric_phase": telluric_phase,
        }
        self.cadence_phase = cadence
        self.cadence_modulation = {
            "glow_intensity": clamp01((micro * 0.25) + (dream * 0.35) + 0.3),
            "rotation_speed": clamp01((cognition * 0.45) + 0.25),
            "trail_decay": clamp01((1.0 - micro) * 0.3 + (reflection * 0.45) + 0.2),
            "swarm_clustering": clamp01((cognition * 0.35) + (telluric * 0.35) + 0.15),
            "halo_breathing": clamp01((dream * 0.4) + (reflection * 0.3) + 0.2),
            "branching_pressure": clamp01((micro * 0.2) + (cognition * 0.3) + (telluric * 0.3) + 0.1),
            "substrate_drift": clamp01((visual * 0.35) + (dream * 0.25) + 0.2),
        }
        return cadence

    def _derive_mirror_state(self, telemetry: dict[str, Any], tacti: dict[str, Any]) -> MirrorState:
        activity = self._get_activity_snapshot(telemetry, tacti)
        self.activity_snapshot = activity
        self.activity_signal = float(activity["activity_signal"])
        self.agent_activity_level = float(activity["agent_activity_level"])
        self.agent_count_active = int(activity["agent_count_active"])
        self.coordination_density = float(activity["coordination_density"])
        self.routing_activity = float(activity["routing_activity"])
        self.interaction_activity = float(activity["interaction_activity"])
        self.memory_activity = float(activity["memory_activity"])
        self.heavy_inference_suppressed = bool(activity["heavy_inference_suppressed"])
        self.semantic_activity_source_summary = str(activity["semantic_activity_source_summary"])

        arousal = clamp01(float(tacti.get("arousal", 0.5) or 0.5))
        memory = clamp01(float(tacti.get("memory_recall_density", 0.0) or 0.0))
        research = clamp01(float(tacti.get("research_depth", 0.0) or 0.0))
        token_flux = clamp01(float(tacti.get("token_flux", 0.0) or 0.0))
        gpu_util = clamp01(float(telemetry.get("gpu_util", 0.0) or 0.0))
        cpu_util = clamp01(float(telemetry.get("cpu_util", telemetry.get("cpu_load", 0.0)) or 0.0))
        cpu_temp = clamp01((float(telemetry.get("cpu_temp", 50.0) or 50.0) - 35.0) / 45.0)
        goal_conflict_present = "goal_conflict" in tacti
        goal_conflict = clamp01(
            float(
                tacti.get(
                    "goal_conflict",
                    (arousal * 0.35) + (token_flux * 0.25) + (cpu_util * 0.2) + (0.2 * max(0.0, self.activity_signal - 0.5)),
                )
                or 0.0
            )
        )

        overload = clamp01(
            (arousal * 0.25)
            + (goal_conflict * 0.2)
            + (token_flux * 0.2)
            + (gpu_util * 0.15)
            + (cpu_util * 0.1)
            + (cpu_temp * 0.1)
        )
        coherence = clamp01(
            ((1.0 - overload) * 0.28)
            + (memory * 0.24)
            + ((1.0 - goal_conflict) * 0.18)
            + (research * 0.15)
            + ((1.0 - arousal) * 0.15)
        )
        learning = clamp01((memory * 0.46) + (research * 0.22) + (coherence * 0.18) + (self.memory_activity * 0.14))
        reasoning = clamp01(
            (research * 0.34)
            + (self.routing_activity * 0.24)
            + (self.coordination_density * 0.18)
            + (self.activity_signal * 0.14)
            + (self.agent_activity_level * 0.1)
            - (overload * 0.1)
        )
        attention = clamp01(
            (arousal * 0.24)
            + (self.activity_signal * 0.24)
            + (self.coordination_density * 0.2)
            + (self.interaction_activity * 0.12)
            + ((1.0 - goal_conflict) * 0.1)
            + (research * 0.1)
        )
        reflection_phase = clamp01(float(getattr(self, "cadence_phase", {}).get("reflection_sweep", 0.5) or 0.5))
        insight = clamp01(
            (reasoning * 0.24)
            + (learning * 0.2)
            + (coherence * 0.18)
            + (self.memory_activity * 0.14)
            + (reflection_phase * 0.12)
            + (self.activity_signal * 0.12)
            - (0.18 if self.heavy_inference_suppressed else 0.0)
        )
        baseline = clamp01(0.35 + (coherence * 0.3) + (learning * 0.15) + (memory * 0.1) - (overload * 0.14))
        collapse_risk = clamp01((overload * 0.58) + (goal_conflict * 0.18) + ((1.0 - coherence) * 0.16) + (cpu_temp * 0.08))
        repair_progress = clamp01(
            (coherence * 0.32)
            + (self.memory_activity * 0.14)
            + (self.coordination_density * 0.12)
            + ((1.0 - collapse_risk) * 0.18)
            + (reflection_phase * 0.12)
            + (learning * 0.12)
        )

        self.mirror_state_inference = {
            "goal_conflict_source": "tacti.goal_conflict" if goal_conflict_present else "derived(arousal, token_flux, cpu_util, activity_signal)",
            "research_depth_source": "tacti.research_depth" if "research_depth" in tacti else "derived(default=0.0)",
            "token_flux_source": "tacti.token_flux" if "token_flux" in tacti else "derived(default=0.0)",
            "activity_signal_source": "runtime.activity_snapshot" if getattr(self, "activity_snapshot", None) else "derived(local_activity)",
            "agent_activity_source": (
                "runtime.activity_snapshot.agent_activity_level" if getattr(self, "activity_snapshot", None) else "derived(active_agents)"
            ),
            "routing_activity_source": (
                "runtime.activity_snapshot.routing_activity" if getattr(self, "activity_snapshot", None) else "derived(research_depth, token_flux)"
            ),
            "reflection_phase_source": "derived(cadence.reflection_sweep)",
            "repair_progress_source": "derived(coherence, overload, collapse_risk, memory_activity, coordination_density)",
        }
        self.mirror_state = MirrorState(
            baseline=baseline,
            reasoning=reasoning,
            insight=insight,
            learning=learning,
            attention=attention,
            overload=overload,
            coherence=coherence,
            reflection_phase=reflection_phase,
            collapse_risk=collapse_risk,
            repair_progress=repair_progress,
        )
        return self.mirror_state

    def _derive_ecosystem_state(self, telemetry: dict[str, Any], tacti: dict[str, Any], mirror: MirrorState) -> dict[str, Any]:
        colony = dict(getattr(self, "colony_memory_state", {}) or {})
        colony_memory_level = clamp01(float(colony.get("colony_memory_level", 0.0) or 0.0))
        route_reinforcement = clamp01(float(colony.get("route_reinforcement", 0.0) or 0.0))
        dormant_zone_ratio = clamp01(float(colony.get("dormant_zone_ratio", 0.0) or 0.0))
        scar_tissue_intensity = clamp01(float(colony.get("scar_tissue_intensity", 0.0) or 0.0))
        repair_zone_intensity = clamp01(float(colony.get("repair_zone_intensity", 0.0) or 0.0))
        stabilized_habitat_ratio = clamp01(float(colony.get("stabilized_habitat_ratio", 0.0) or 0.0))
        ecological_persistence = clamp01(float(colony.get("ecological_persistence", colony_memory_level) or colony_memory_level))
        memory_flux = clamp01(float(colony.get("memory_flux", 0.0) or 0.0))

        display_active = bool(getattr(self, "display_mode_active", False))
        session_seconds = float(getattr(self, "_dreamscape_session_seconds", 0.0) or 0.0)
        session_progress = clamp01(session_seconds / 480.0)
        arousal = clamp01(float(tacti.get("arousal", 0.5) or 0.5))
        memory = clamp01(float(tacti.get("memory_recall_density", 0.0) or 0.0))
        research = clamp01(float(tacti.get("research_depth", 0.0) or 0.0))
        token_flux = clamp01(float(tacti.get("token_flux", 0.0) or 0.0))
        active_agent_norm = clamp01(min(1.0, self.agent_count_active / 6.0))

        ecosystem_activity = clamp01(
            (self.activity_signal * 0.28)
            + (arousal * 0.18)
            + (research * 0.16)
            + (token_flux * 0.12)
            + (mirror.reasoning * 0.12)
            + (mirror.learning * 0.14)
        )
        previous_memory = clamp01(float(getattr(self, "ecosystem_state", {}).get("ecological_memory", ecological_persistence) or ecological_persistence))
        ecological_memory = clamp01((previous_memory * 0.86) + ((ecosystem_activity * 0.48) + (ecological_persistence * 0.26) + (memory * 0.16) + (route_reinforcement * 0.1)) * 0.14)
        growth_front_intensity = clamp01((ecosystem_activity * 0.44) + (arousal * 0.2) + (self.activity_signal * 0.12) + (active_agent_norm * 0.12) + (0.12 * session_progress))
        decay_field_intensity = clamp01((mirror.collapse_risk * 0.44) + (scar_tissue_intensity * 0.26) + (dormant_zone_ratio * 0.18) + ((1.0 - ecosystem_activity) * 0.12))
        synchronization_pulse = clamp01((self.coordination_density * 0.48) + (mirror.coherence * 0.26) + (float(self.cadence_phase.get("micro_pulse", 0.5)) * 0.16) + (route_reinforcement * 0.1))
        substrate_excitation = clamp01((growth_front_intensity * 0.5) + (arousal * 0.18) + (self.routing_activity * 0.12) + (float(self.cadence_phase.get("cognition_cycle", 0.5)) * 0.2))
        active_colony_area = clamp01((ecosystem_activity * 0.22) + (session_progress * 0.12) + (ecological_memory * 0.1) + (active_agent_norm * 0.08))
        landscape_maturity = clamp01((ecosystem_activity * 0.22) + (session_progress * 0.18) + (ecological_memory * 0.14) + (mirror.coherence * 0.1))
        habitat_complexity = clamp01((landscape_maturity * 0.56) + (stabilized_habitat_ratio * 0.14) + (mirror.reasoning * 0.12) + (route_reinforcement * 0.08))
        dreamscape_density = clamp01(max(0.0, (landscape_maturity - 0.22) * 0.42) + (ecological_memory * 0.08))
        void_ratio = clamp01(1.0 - ((active_colony_area * 0.58) + (landscape_maturity * 0.28) + (dreamscape_density * 0.1) + (ecological_memory * 0.08)))
        colony_stability = clamp01((mirror.coherence * 0.34) + (ecological_memory * 0.24) + (stabilized_habitat_ratio * 0.16) + ((1.0 - decay_field_intensity) * 0.16) + (route_reinforcement * 0.1))
        thriving_region_ratio = clamp01((colony_stability * 0.42) + (growth_front_intensity * 0.18) + (habitat_complexity * 0.18) + (session_progress * 0.12))
        contested_region_ratio = clamp01((mirror.overload * 0.3) + (mirror.collapse_risk * 0.22) + (growth_front_intensity * 0.16) + ((1.0 - colony_stability) * 0.18) + (self.interaction_activity * 0.14))
        dormant_region_ratio = clamp01((void_ratio * 0.3) + (dormant_zone_ratio * 0.28) + ((1.0 - ecosystem_activity) * 0.22) + (scar_tissue_intensity * 0.2))
        territory_entropy = clamp01((contested_region_ratio * 0.34) + (void_ratio * 0.2) + (growth_front_intensity * 0.16) + ((1.0 - route_reinforcement) * 0.16) + (0.14 * (1.0 - synchronization_pulse)))
        microbe_density = clamp01((ecosystem_activity * 0.26) + (growth_front_intensity * 0.24) + (active_colony_area * 0.16) + (session_progress * 0.08))
        division_rate = clamp01((growth_front_intensity * 0.42) + (substrate_excitation * 0.18) + (active_agent_norm * 0.12) + ((1.0 - void_ratio) * 0.12) + (0.16 * (1.0 - mirror.overload)))
        substrate_health = clamp01((mirror.coherence * 0.26) + (colony_stability * 0.24) + ((1.0 - decay_field_intensity) * 0.18) + (repair_zone_intensity * 0.16) + (ecological_memory * 0.16))
        morphogenesis_level = clamp01((active_colony_area * 0.3) + (landscape_maturity * 0.22) + (mirror.reasoning * 0.14) + (mirror.learning * 0.14) + (growth_front_intensity * 0.2))
        membrane_density = clamp01((colony_stability * 0.22) + (ecological_memory * 0.22) + (repair_zone_intensity * 0.16) + (habitat_complexity * 0.14) + (0.14 * session_progress))
        filament_activity = clamp01((route_reinforcement * 0.28) + (growth_front_intensity * 0.22) + (self.routing_activity * 0.18) + (microbe_density * 0.14) + (0.18 * float(self.cadence_modulation.get("branching_pressure", 0.0))))
        necrosis_front_intensity = clamp01((scar_tissue_intensity * 0.32) + (decay_field_intensity * 0.28) + (mirror.collapse_risk * 0.22) + (dormant_region_ratio * 0.18))
        district_entropy = clamp01((territory_entropy * 0.42) + (contested_region_ratio * 0.2) + ((1.0 - habitat_complexity) * 0.18) + (void_ratio * 0.2))
        route_ecology_strength = clamp01((route_reinforcement * 0.28) + (self.routing_activity * 0.24) + (filament_activity * 0.18) + (synchronization_pulse * 0.14) + (ecological_memory * 0.16))
        colony_competition = clamp01((contested_region_ratio * 0.42) + (mirror.overload * 0.18) + (growth_front_intensity * 0.18) + ((1.0 - synchronization_pulse) * 0.12) + (void_ratio * 0.1))
        colony_recovery = clamp01((mirror.repair_progress * 0.34) + (substrate_health * 0.22) + (repair_zone_intensity * 0.16) + (ecological_memory * 0.14) + (colony_stability * 0.14))
        automata_phase = clamp01((growth_front_intensity * 0.36) + (float(self.cadence_phase.get("micro_pulse", 0.5)) * 0.22) + (division_rate * 0.16) + (route_ecology_strength * 0.12) + (0.14 * (1.0 - void_ratio)))
        archetype_emergence_level = clamp01((morphogenesis_level * 0.26) + (habitat_complexity * 0.2) + (mirror.insight * 0.18) + (mirror.reasoning * 0.12) + (dreamscape_density * 0.12) + (ecological_memory * 0.12))
        ocular_emergence = clamp01((mirror.attention * 0.34) + (mirror.reasoning * 0.22) + (route_ecology_strength * 0.18) + (self.activity_signal * 0.14) + (archetype_emergence_level * 0.12))
        rib_emergence = clamp01((membrane_density * 0.34) + (colony_stability * 0.22) + (route_ecology_strength * 0.12) + (substrate_health * 0.18) + (archetype_emergence_level * 0.14))
        wing_emergence = clamp01((mirror.insight * 0.28) + (dreamscape_density * 0.18) + (ritual_coherence if "ritual_coherence" in locals() else 0.0))
        spine_emergence = clamp01((filament_activity * 0.32) + (route_ecology_strength * 0.28) + (mirror.reasoning * 0.14) + (growth_front_intensity * 0.14) + (archetype_emergence_level * 0.12))
        gear_ossification = clamp01((mirror.reasoning * 0.32) + (self.routing_activity * 0.22) + (route_ecology_strength * 0.18) + ((1.0 - mirror.overload) * 0.12) + (archetype_emergence_level * 0.16))
        angelic_presence = clamp01((mirror.coherence * 0.34) + (mirror.repair_progress * 0.2) + (dreamscape_density * 0.12) + (self.memory_activity * 0.12) + (archetype_emergence_level * 0.22))
        daemonic_pressure = clamp01((mirror.collapse_risk * 0.34) + (mirror.overload * 0.24) + (decay_field_intensity * 0.2) + (contested_region_ratio * 0.12) + (void_ratio * 0.1))
        serpentine_force = clamp01((filament_activity * 0.22) + (route_ecology_strength * 0.24) + (contested_region_ratio * 0.12) + (mirror.reasoning * 0.14) + (archetype_emergence_level * 0.18) + (0.1 * float(self.cadence_phase.get("telluric_resonance", 0.0))))
        trickster_play = clamp01((self.activity_signal * 0.18) + (self.interaction_activity * 0.24) + (automata_phase * 0.14) + (territory_entropy * 0.18) + (archetype_emergence_level * 0.12) + (0.14 * float(self.cadence_phase.get("micro_pulse", 0.0))))
        ritual_coherence = clamp01((mirror.coherence * 0.34) + (synchronization_pulse * 0.24) + (route_ecology_strength * 0.16) + (archetype_emergence_level * 0.14) + (self.memory_activity * 0.12))
        wing_emergence = clamp01((mirror.insight * 0.28) + (dreamscape_density * 0.18) + (ritual_coherence * 0.24) + (angelic_presence * 0.16) + (0.14 * float(self.cadence_phase.get("dream_cadence", 0.0))))

        seed_region_count = max(1, int(round(1.0 + (active_colony_area * 10.0) + (session_progress * 2.0) + (active_agent_norm * 2.0))))
        if display_active and session_seconds >= 60.0:
            seed_region_count = max(seed_region_count, 2)
        colony_count_estimate = max(seed_region_count, int(round(2.0 + (microbe_density * 12.0) + (route_ecology_strength * 6.0))))
        nursery_count = max(0, int(round((habitat_complexity * 10.0) + (colony_recovery * 6.0))))

        cathedral_scene_weight = clamp01((angelic_presence * 0.26) + (ritual_coherence * 0.22) + (gear_ossification * 0.16) + (mirror.reasoning * 0.12) + (habitat_complexity * 0.24))
        ossuary_scene_weight = clamp01((daemonic_pressure * 0.28) + (necrosis_front_intensity * 0.24) + (void_ratio * 0.14) + (territory_entropy * 0.16) + (gear_ossification * 0.18))
        labyrinth_scene_weight = clamp01((route_ecology_strength * 0.3) + (territory_entropy * 0.18) + (spine_emergence * 0.18) + (gear_ossification * 0.14) + (mirror.reasoning * 0.2))
        carnival_scene_weight = clamp01((trickster_play * 0.34) + (self.interaction_activity * 0.18) + (wing_emergence * 0.1) + (territory_entropy * 0.18) + (archetype_emergence_level * 0.2))
        hybrid_plaza_weight = clamp01((cathedral_scene_weight * 0.22) + (labyrinth_scene_weight * 0.2) + (carnival_scene_weight * 0.18) + (ecosystem_activity * 0.18) + (mirror.coherence * 0.12) + (serpentine_force * 0.1))

        self.colony_memory_state = {
            "colony_memory_level": clamp01((colony_memory_level * 0.88) + (ecological_memory * 0.12)),
            "route_reinforcement": clamp01((route_reinforcement * 0.84) + (route_ecology_strength * 0.16)),
            "dormant_zone_ratio": clamp01((dormant_zone_ratio * 0.84) + (dormant_region_ratio * 0.16)),
            "scar_tissue_intensity": clamp01((scar_tissue_intensity * 0.82) + (necrosis_front_intensity * 0.18)),
            "repair_zone_intensity": clamp01((repair_zone_intensity * 0.82) + (colony_recovery * 0.18)),
            "stabilized_habitat_ratio": clamp01((stabilized_habitat_ratio * 0.84) + (habitat_complexity * 0.16)),
            "ecological_persistence": clamp01((ecological_persistence * 0.88) + (ecological_memory * 0.12)),
            "memory_flux": clamp01((memory_flux * 0.7) + (abs(ecological_memory - previous_memory) * 0.3)),
        }

        state = {
            "ecosystem_activity": ecosystem_activity,
            "colony_stability": colony_stability,
            "growth_front_intensity": growth_front_intensity,
            "decay_field_intensity": decay_field_intensity,
            "synchronization_pulse": synchronization_pulse,
            "substrate_excitation": substrate_excitation,
            "void_ratio": void_ratio,
            "active_colony_area": active_colony_area,
            "dreamscape_density": dreamscape_density,
            "landscape_maturity": landscape_maturity,
            "landscape_session_seconds": clamp01(session_seconds / 1200.0),
            "colony_count_estimate": colony_count_estimate,
            "dormant_region_ratio": dormant_region_ratio,
            "thriving_region_ratio": thriving_region_ratio,
            "contested_region_ratio": contested_region_ratio,
            "territory_entropy": territory_entropy,
            "microbe_density": microbe_density,
            "division_rate": division_rate,
            "substrate_health": substrate_health,
            "morphogenesis_level": morphogenesis_level,
            "membrane_density": membrane_density,
            "filament_activity": filament_activity,
            "necrosis_front_intensity": necrosis_front_intensity,
            "habitat_complexity": habitat_complexity,
            "nursery_count": nursery_count,
            "district_entropy": district_entropy,
            "route_ecology_strength": route_ecology_strength,
            "automata_phase": automata_phase,
            "colony_competition": colony_competition,
            "colony_recovery": colony_recovery,
            "ecological_memory": ecological_memory,
            "seed_region_count": seed_region_count,
            "ocular_emergence": ocular_emergence,
            "rib_emergence": rib_emergence,
            "wing_emergence": wing_emergence,
            "spine_emergence": spine_emergence,
            "gear_ossification": gear_ossification,
            "angelic_presence": angelic_presence,
            "daemonic_pressure": daemonic_pressure,
            "serpentine_force": serpentine_force,
            "trickster_play": trickster_play,
            "ritual_coherence": ritual_coherence,
            "archetype_emergence_level": archetype_emergence_level,
            "cathedral_scene_weight": cathedral_scene_weight,
            "ossuary_scene_weight": ossuary_scene_weight,
            "labyrinth_scene_weight": labyrinth_scene_weight,
            "carnival_scene_weight": carnival_scene_weight,
            "hybrid_plaza_weight": hybrid_plaza_weight,
        }
        self.ecosystem_state = state
        self.collapse_visual_intensity = clamp01((mirror.collapse_risk * 0.68) + (decay_field_intensity * 0.16) + (daemonic_pressure * 0.16))
        self.repair_visual_intensity = clamp01((mirror.repair_progress * 0.56) + (colony_recovery * 0.22) + (angelic_presence * 0.22))
        self.wild_layer_activation = {
            "orchard_density": clamp01((dreamscape_density * 0.44) + (microbe_density * 0.18) + (angelic_presence * 0.14)),
            "orchard_bloom_state": clamp01((ritual_coherence * 0.36) + (dreamscape_density * 0.22) + (wing_emergence * 0.16)),
            "reservoir_activation": clamp01((ecological_memory * 0.38) + (mirror.insight * 0.16) + (cathedral_scene_weight * 0.12)),
            "reservoir_depth": clamp01((void_ratio * 0.18) + (ecological_memory * 0.26) + (ossuary_scene_weight * 0.18) + (labyrinth_scene_weight * 0.1)),
            "relay_serpent_activity": clamp01((serpentine_force * 0.54) + (route_ecology_strength * 0.26)),
            "chronofossil_intensity": clamp01((ecological_memory * 0.28) + (ossuary_scene_weight * 0.24) + (mirror.reflection_phase * 0.18)),
            "moth_activity": clamp01((carnival_scene_weight * 0.34) + (dreamscape_density * 0.18) + (trickster_play * 0.24)),
            "moth_cluster_count": float(max(1, int(round(4 + (carnival_scene_weight * 8.0))))),
        }
        return state

    def _derive_scene_attractors(self) -> dict[str, dict[str, float]]:
        ecosystem = dict(getattr(self, "ecosystem_state", {}) or {})
        mirror = getattr(self, "mirror_state", MirrorState())
        def _strength(key: str) -> float:
            return clamp01(float(ecosystem.get(key, 0.0) or 0.0))

        attractors = {
            "cathedral": {
                "x": clamp01(0.5 - _strength("cathedral_scene_weight")) * -1.0,
                "y": clamp01(0.55 - mirror.coherence * 0.5) * -0.8,
                "radius": clamp01(0.18 + (_strength("cathedral_scene_weight") * 0.35)),
                "strength": _strength("cathedral_scene_weight"),
            },
            "ossuary": {
                "x": clamp01(0.25 + _strength("ossuary_scene_weight") * 0.65),
                "y": clamp01(0.2 + _strength("void_ratio") * 0.6),
                "radius": clamp01(0.16 + (_strength("ossuary_scene_weight") * 0.28)),
                "strength": _strength("ossuary_scene_weight"),
            },
            "labyrinth": {
                "x": clamp01(0.18 + _strength("route_ecology_strength") * 0.5),
                "y": clamp01(0.5 - _strength("territory_entropy")) * -1.0,
                "radius": clamp01(0.2 + (_strength("labyrinth_scene_weight") * 0.28)),
                "strength": _strength("labyrinth_scene_weight"),
            },
            "carnival": {
                "x": clamp01(0.56 - _strength("carnival_scene_weight")) * -1.0,
                "y": clamp01(0.22 + _strength("trickster_play") * 0.58),
                "radius": clamp01(0.16 + (_strength("carnival_scene_weight") * 0.22)),
                "strength": _strength("carnival_scene_weight"),
            },
            "hybrid": {
                "x": clamp01(0.5 + (mirror.reasoning - mirror.overload) * 0.5) * 2.0 - 1.0,
                "y": clamp01(0.5 + (mirror.learning - mirror.collapse_risk) * 0.5) * 2.0 - 1.0,
                "radius": clamp01(0.22 + (_strength("hybrid_plaza_weight") * 0.24)),
                "strength": _strength("hybrid_plaza_weight"),
            },
        }
        for row in attractors.values():
            row["x"] = max(-1.0, min(1.0, float(row["x"])))
            row["y"] = max(-1.0, min(1.0, float(row["y"])))
            row["radius"] = clamp01(float(row["radius"]))
            row["strength"] = clamp01(float(row["strength"]))
        self.scene_attractors = attractors
        return attractors

    def _derive_motif_activation(self, mirror: MirrorState) -> dict[str, float]:
        ecosystem = dict(getattr(self, "ecosystem_state", {}) or {})
        activity_signal = float(getattr(self, "activity_signal", 0.0) or 0.0)
        routing_activity = float(getattr(self, "routing_activity", 0.0) or 0.0)
        coordination_density = float(getattr(self, "coordination_density", 0.0) or 0.0)
        agent_activity_level = float(getattr(self, "agent_activity_level", 0.0) or 0.0)
        interaction_activity = float(getattr(self, "interaction_activity", 0.0) or 0.0)
        memory_activity = float(getattr(self, "memory_activity", 0.0) or 0.0)
        cadence_phase = dict(getattr(self, "cadence_phase", {}) or {})
        motif = {
            "identity_core": 1.0,
            "eye": clamp01((mirror.attention * 0.3) + (mirror.reasoning * 0.18) + (activity_signal * 0.2) + (mirror.baseline * 0.18) + 0.22),
            "clockwork": clamp01((mirror.reasoning * 0.32) + (routing_activity * 0.18) + (coordination_density * 0.16) + ((1.0 - mirror.overload) * 0.14) + 0.08),
            "halo": clamp01((mirror.coherence * 0.41) + (mirror.repair_progress * 0.16) + (activity_signal * 0.2) + (mirror.baseline * 0.22) + (mirror.reflection_phase * 0.1) + 0.19),
            "murmuration": clamp01((activity_signal * 0.26) + (coordination_density * 0.22) + (agent_activity_level * 0.16) + (float(cadence_phase.get("micro_pulse", 0.5)) * 0.18) + 0.08),
            "slime_trails": clamp01((activity_signal * 0.3) + (routing_activity * 0.24) + (float(ecosystem.get("growth_front_intensity", 0.0) or 0.0) * 0.18) + (float(ecosystem.get("membrane_density", 0.0) or 0.0) * 0.12) + 0.2),
            "memory_constellations": clamp01((mirror.learning * 0.26) + (memory_activity * 0.22) + (mirror.reflection_phase * 0.18) + (mirror.coherence * 0.12) + 0.06),
            "profile_bias_cathedral": clamp01(float(getattr(self, "motif_weights", {}).get("cathedral", 0.92))),
        }
        self.motif_activation = motif
        return motif

    def _derive_novel_layer_activation(self, mirror: MirrorState) -> dict[str, float]:
        motif = dict(getattr(self, "motif_activation", {}) or {})
        ecosystem = dict(getattr(self, "ecosystem_state", {}) or {})
        novel = {
            "automaton_caravans": clamp01((float(motif.get("clockwork", 0.0)) * 0.42) + (self.routing_activity * 0.18) + (float(ecosystem.get("route_ecology_strength", 0.0)) * 0.18) + (mirror.reasoning * 0.12) + 0.08),
            "mycelial_veins": clamp01((float(motif.get("slime_trails", 0.0)) * 0.34) + (float(ecosystem.get("growth_front_intensity", 0.0)) * 0.18) + (float(ecosystem.get("ecological_memory", 0.0)) * 0.18) + (self.activity_signal * 0.14) + 0.08),
            "sigil_blooms": clamp01((float(motif.get("halo", 0.0)) * 0.26) + (mirror.insight * 0.2) + (float(ecosystem.get("ritual_coherence", 0.0)) * 0.18) + (self.interaction_activity * 0.14) + 0.08),
            "chrysalis_nests": clamp01((float(motif.get("memory_constellations", 0.0)) * 0.22) + (float(ecosystem.get("ecological_memory", 0.0)) * 0.24) + (mirror.learning * 0.18) + (float(ecosystem.get("colony_stability", 0.0)) * 0.14) + 0.08),
            "spore_bursts": clamp01((float(motif.get("murmuration", 0.0)) * 0.22) + (self.activity_signal * 0.18) + (float(ecosystem.get("division_rate", 0.0)) * 0.2) + (float(ecosystem.get("growth_front_intensity", 0.0)) * 0.12) + 0.08),
        }
        self.novel_layer_activation = novel
        return novel

    def _derive_state_hue_mix(self, mirror: MirrorState) -> dict[str, Any]:
        raw = {
            "indigo_violet": 0.22 + (mirror.baseline * 0.18) + (mirror.reflection_phase * 0.08),
            "electric_blue": 0.12 + (mirror.reasoning * 0.18) + (self.routing_activity * 0.08),
            "gold": 0.1 + (mirror.insight * 0.16) + (float(self.ecosystem_state.get("ritual_coherence", 0.0)) * 0.08),
            "emerald": 0.1 + (mirror.learning * 0.16) + (self.memory_activity * 0.08),
            "amber": 0.08 + (self.activity_signal * 0.16) + (float(self.ecosystem_state.get("growth_front_intensity", 0.0)) * 0.08),
            "crimson": 0.06 + (mirror.collapse_risk * 0.18) + (float(self.ecosystem_state.get("daemonic_pressure", 0.0)) * 0.08),
            "white": 0.08 + (mirror.coherence * 0.16) + (mirror.repair_progress * 0.08),
        }
        total = sum(raw.values()) or 1.0
        mix = {key: float(value) / total for key, value in raw.items()}
        mix["semantic_energy"] = clamp01((self.activity_signal * 0.24) + (mirror.reasoning * 0.18) + (mirror.insight * 0.18) + (mirror.learning * 0.16) + (mirror.coherence * 0.14))
        mix["semantic_weights_a"] = [mirror.baseline, mirror.reasoning, mirror.insight, mirror.learning]
        mix["semantic_weights_b"] = [mirror.attention, mirror.overload, mirror.coherence, mirror.reflection_phase]
        self.state_hue_mix = mix
        return mix

    def _ecosystem_uniform_vectors(self) -> tuple[list[float], list[float], list[float]]:
        ecosystem = dict(getattr(self, "ecosystem_state", {}) or {})
        row_a = [
            clamp01(float(ecosystem.get("ecosystem_activity", 0.0) or 0.0)),
            clamp01(float(ecosystem.get("colony_stability", 0.0) or 0.0)),
            clamp01(float(ecosystem.get("growth_front_intensity", 0.0) or 0.0)),
            clamp01(float(ecosystem.get("decay_field_intensity", 0.0) or 0.0)),
        ]
        row_b = [
            clamp01(float(ecosystem.get("synchronization_pulse", 0.0) or 0.0)),
            clamp01(float(ecosystem.get("substrate_excitation", 0.0) or 0.0)),
            clamp01(min(1.0, float(ecosystem.get("colony_count_estimate", 0.0) or 0.0) / 24.0)),
            clamp01(float(ecosystem.get("automata_phase", 0.0) or 0.0)),
        ]
        row_c = [
            clamp01(float(ecosystem.get("colony_competition", 0.0) or 0.0)),
            clamp01(float(ecosystem.get("colony_recovery", 0.0) or 0.0)),
            clamp01(float(ecosystem.get("ecological_memory", 0.0) or 0.0)),
            clamp01(float(ecosystem.get("dormant_region_ratio", 0.0) or 0.0)),
        ]
        return row_a, row_b, row_c

    def _ecosystem_stage_uniform_vector(self) -> list[float]:
        ecosystem = dict(getattr(self, "ecosystem_state", {}) or {})
        return [
            clamp01(float(ecosystem.get("active_colony_area", 0.0) or 0.0)),
            clamp01(float(ecosystem.get("landscape_maturity", 0.0) or 0.0)),
            clamp01(float(ecosystem.get("habitat_complexity", 0.0) or 0.0)),
            clamp01(float(ecosystem.get("dreamscape_density", 0.0) or 0.0)),
        ]

    def _scene_attractor_uniform_vectors(self) -> list[list[float]]:
        attractors = dict(getattr(self, "scene_attractors", {}) or {})
        rows: list[list[float]] = []
        for name in ("cathedral", "ossuary", "labyrinth", "carnival", "hybrid"):
            row = attractors.get(name, {})
            rows.append(
                [
                    max(-1.0, min(1.0, float(row.get("x", 0.0) or 0.0))),
                    max(-1.0, min(1.0, float(row.get("y", 0.0) or 0.0))),
                    clamp01(float(row.get("radius", 0.0) or 0.0)),
                    clamp01(float(row.get("strength", 0.0) or 0.0)),
                ]
            )
        return rows

    def _motif_uniform_vectors(self) -> tuple[list[float], list[float]]:
        motif = dict(getattr(self, "motif_activation", {}) or {})
        mirror = getattr(self, "mirror_state", MirrorState())
        row_a = [
            clamp01(float(motif.get("identity_core", 1.0) or 1.0)),
            clamp01(float(motif.get("eye", 0.0) or 0.0)),
            clamp01(float(motif.get("clockwork", 0.0) or 0.0)),
            clamp01(float(motif.get("halo", 0.0) or 0.0)),
        ]
        row_b = [
            clamp01(float(motif.get("murmuration", 0.0) or 0.0)),
            clamp01(float(motif.get("slime_trails", 0.0) or 0.0)),
            clamp01(float(motif.get("memory_constellations", 0.0) or 0.0)),
            clamp01(max(mirror.collapse_risk, mirror.overload, float(getattr(self, "collapse_visual_intensity", 0.0) or 0.0))),
        ]
        return row_a, row_b

    def _cadence_uniform_vector(self) -> list[float]:
        phase = dict(getattr(self, "cadence_phase", {}) or {})
        return [
            clamp01(float(phase.get("micro_pulse", 0.0) or 0.0)),
            clamp01(float(phase.get("cognition_cycle", 0.0) or 0.0)),
            clamp01(float(phase.get("reflection_sweep", 0.0) or 0.0)),
            clamp01(float(phase.get("dream_cadence", 0.0) or 0.0)),
        ]

    def _state_transition_vector(self) -> list[float]:
        mirror = getattr(self, "mirror_state", MirrorState())
        return [
            clamp01(float(mirror.collapse_risk)),
            clamp01(float(mirror.repair_progress)),
            clamp01(float(mirror.coherence)),
            clamp01(float(mirror.overload)),
        ]

    def update_signals(self, telemetry: dict[str, Any], tacti: dict[str, Any]) -> None:
        now_ts = time.time()
        mask_model = self._mask_model_features()
        fan_speed = telemetry.get("fan_gpu") if telemetry.get("fan_gpu") is not None else telemetry.get("fan_cpu")
        raw_token_flux = float(tacti.get("token_flux", 0.0) or 0.0)
        raw_local_model_loading = 1.0 if bool(telemetry.get("local_model_loading") or tacti.get("local_model_loading")) else 0.0
        raw_kv_cache_mb = float(telemetry.get("kv_cache_mb", 0.0) or 0.0)
        raw_model_vram = telemetry.get("model_vram_mb_by_process", 0.0)
        model_vram_mb = 0.0
        if isinstance(raw_model_vram, dict):
            model_vram_mb = float(sum(float(v or 0.0) for v in raw_model_vram.values()))
        elif isinstance(raw_model_vram, list):
            model_vram_mb = float(sum(float(v or 0.0) for v in raw_model_vram))
        else:
            model_vram_mb = float(raw_model_vram or 0.0)
        self.features = {
            "gpu_temp": {"value": float(telemetry.get("gpu_temp", 0.0) or 0.0), "present": telemetry.get("gpu_temp") is not None},
            "gpu_util": {"value": float(telemetry.get("gpu_util", 0.0) or 0.0), "present": True},
            "gpu_vram_ratio": {"value": float(telemetry.get("gpu_vram", 0.0) or 0.0), "present": True},
            "gpu_vram_used_mb": {"value": float(telemetry.get("gpu_vram_used_mb", 0.0) or 0.0), "present": True},
            "fan_speed": {"value": float(fan_speed or 0.0), "present": fan_speed is not None},
            "disk_io": {"value": float(telemetry.get("disk_io", 0.0) or 0.0), "present": True},
            "network_throughput": {"value": float(telemetry.get("network_throughput", 0.0) or 0.0), "present": True},
            "token_flux": {"value": (0.0 if mask_model else raw_token_flux), "present": (not mask_model)},
            "local_model_loading": {"value": (0.0 if mask_model else raw_local_model_loading), "present": (not mask_model)},
            "kv_cache_mb": {"value": (0.0 if mask_model else raw_kv_cache_mb), "present": (not mask_model)},
            "model_vram_mb_by_process": {"value": (0.0 if mask_model else model_vram_mb), "present": (not mask_model)},
        }
        self.features_masked = (
            ["token_flux", "local_model_loading", "kv_cache_mb", "model_vram_mb_by_process"] if mask_model else []
        )
        self.novelty_seed_source = "hardware" if mask_model else "mixed"
        self.signals = RendererSignals(
            arousal=float(tacti.get("arousal", 0.5) or 0.5),
            gpu_temp=float(telemetry.get("gpu_temp", 0.0) or 0.0),
            gpu_util=float(telemetry.get("gpu_util", 0.0) or 0.0),
            gpu_vram=float(telemetry.get("gpu_vram", 0.0) or 0.0),
            gpu_vram_used_mb=float(telemetry.get("gpu_vram_used_mb", 0.0) or 0.0),
            cpu_temp=float(telemetry.get("cpu_temp", 50.0) or 50.0),
            fan_speed=float(fan_speed or 1200.0),
            disk_io=float(telemetry.get("disk_io", 0.0) or 0.0),
            memory_density=float(tacti.get("memory_recall_density", 0.0) or 0.0),
        )
        if mask_model:
            self._rd_inject_seed = float(self._hardware_seed_value(telemetry, now_ts) % 10000) / 10000.0
        # Visual mapping layer.
        self.shader_params["luminosity"] = clamp01(0.25 + self.signals.arousal * 0.75)
        self.shader_params["turbulence"] = clamp01(0.15 + self.signals.arousal * 0.65)
        self.shader_params["velocity"] = clamp01(0.1 + self.signals.gpu_util * 0.9)
        self.shader_params["nebula"] = clamp01(0.2 + self.signals.gpu_vram * 0.8)
        self.shader_params["warmth"] = clamp01((self.signals.cpu_temp - 30.0) / 60.0)
        self.shader_params["vortex"] = clamp01((self.signals.fan_speed - 600.0) / 2200.0)
        self.shader_params["ripple"] = clamp01(self.signals.disk_io)
        self.shader_params["cloud"] = clamp01(self.signals.memory_density)
        self._derive_cadence_phase()
        mirror = self._derive_mirror_state(telemetry, tacti)
        self._derive_ecosystem_state(telemetry, tacti, mirror)
        self._derive_scene_attractors()
        self._derive_motif_activation(mirror)
        self._derive_novel_layer_activation(mirror)
        self._derive_state_hue_mix(mirror)

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
        if self.work_mode_enabled:
            self._work_mode_step(dt)
            self._sync_gpu_particle_buffers()
            return
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
                    (0.35
                    + (self.control_values.get("curiosity_impulse", 0.0) * 1.0)
                    + (self.control_values.get("turbulence_boost", 0.0) * 0.35)
                    + (self.shader_params.get("cloud", 0.0) * 0.5))
                    * self.layer_weight_rd,
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
            self._vol_prog["palette_mode"].value = int(self._palette_mode_index())
            self._vol_prog["white_balance"].value = tuple(float(v) for v in self.white_balance)
            self._vol_prog["layer_weight_rd"].value = float(self.layer_weight_rd)
            self._vol_prog["layer_weight_volume"].value = float(self.layer_weight_volume)
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
        particle_weight = max(0.1, float(self.layer_weight_particles))
        self._prog["point_size"].value = (
            1.7
            + (self.shader_params["nebula"] * 2.4)
            + max(0.0, self.control_values["density_boost"] - 1.0) * 2.4
            + (curiosity_pulse * 2.6)
        ) * (0.75 + 0.5 * particle_weight)
        self._prog["warmth"].value = self.shader_params["warmth"]
        self._prog["luminosity"].value = self.shader_params["luminosity"] * particle_weight
        self._prog["exposure"].value = self.effective_exposure
        self._prog["contrast"].value = self.effective_contrast
        self._prog["saturation"].value = self.effective_saturation
        self._prog["bloom"].value = self.effective_bloom
        self._prog["palette_mode"].value = int(self._palette_mode_index())
        self._prog["white_balance"].value = tuple(float(v) for v in self.white_balance)
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
            self._bloom_extract_prog["threshold"].value = float(self.bloom_threshold)
            self._bloom_extract_prog["knee"].value = float(self.bloom_knee)
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
        self._tonemap_prog["hdr_clamp"].value = float(self.hdr_clamp)
        self._tonemap_prog["debug_luma"].value = 1 if self.debug_luma else 0
        self._quad.render(mode=moderngl.TRIANGLE_STRIP)
        luma_est = max(
            0.0,
            (
                0.62 * float(self.vol_luminance_mean)
                + 0.26 * float(self.shader_params.get("luminosity", 0.0))
                + 0.12 * float(self.effective_bloom)
            ),
        )
        self.luminance_mean = (self.luminance_mean * 0.84) + (luma_est * 0.16)
        max_est = min(self.hdr_clamp * 1.25, luma_est * (1.8 + 0.6 * self.control_values.get("curiosity_impulse", 0.0)))
        self.luminance_max = (self.luminance_max * 0.78) + (max_est * 0.22)
        overflow = max(0.0, self.luminance_max - (self.hdr_clamp * 0.92))
        self.clipped_fraction_est = max(0.0, min(1.0, overflow / max(0.4, self.hdr_clamp)))

    def render_scene(self) -> None:
        if self.backend == "tk-work-window":
            self._render_software_scene()
            return
        if not self.gpu_mode:
            return
        try:
            if self._window is None or glfw is None:
                return
            glfw.make_context_current(self._window)
            glfw.poll_events()
            if glfw.window_should_close(self._window):
                try:
                    glfw.set_window_should_close(self._window, False)
                except Exception:
                    pass
                now = time.monotonic()
                if (now - self._last_window_close_log_ts) >= 2.0:
                    self._last_window_close_log_ts = now
                    self.log.log("render_window_close_ignored", backend=self.backend)
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

    def _render_software_scene(self) -> None:
        root = self._software_window
        canvas = self._software_canvas
        if root is None or canvas is None:
            return
        if self._software_window_closed:
            self.log.log("software_backend_window_closed", backend=self.backend)
            self._teardown_gpu_backend()
            return
        now = time.monotonic()
        if (now - self._software_last_render_ts) < 0.12:
            try:
                root.update_idletasks()
                root.update()
            except Exception as exc:
                self.log.log("software_backend_update_failed", error=str(exc))
                self._teardown_gpu_backend()
            return
        self._software_last_render_ts = now
        try:
            cell = max(1, int(self._software_cell_size or 5))
            width = max(1, int(canvas.winfo_width() or 1))
            height = max(1, int(canvas.winfo_height() or 1))
            if getattr(self, "_work_scene", "cellular_automata") == "fantasy_landscape":
                self._render_fantasy_landscape_scene(canvas, width, height, now)
                root.update_idletasks()
                root.update()
                return
            if getattr(self, "_work_scene", "cellular_automata") == "therapeutic_bilateral":
                self._render_therapeutic_bilateral_scene(canvas, width, height, now)
                root.update_idletasks()
                root.update()
                return
            canvas.delete("bg")
            canvas.delete("pulse")
            canvas.delete("cell")
            canvas.delete("halo")
            canvas.delete("junction")
            twinkle_phase = float(self.frame_index) * (0.035 * float(getattr(self, "_work_visual_time_scale", 1.0)))
            for idx, (sx, sy, seed) in enumerate(self._software_starfield):
                px = int(sx * width)
                py = int(sy * height)
                pulse = 0.35 + (0.18 * math.sin((seed * 7.0) + twinkle_phase + (idx * 0.13)))
                shade = int(10 + (12 * pulse))
                color = f"#{shade:02x}{shade:02x}{min(42, shade + 10):02x}"
                canvas.create_oval(px, py, px + 1, py + 1, fill=color, outline="", tags="bg")
            if getattr(self, "_work_pulses_enabled", False):
                for pulse in self._work_recent_pulses:
                    life = max(0.0, min(1.0, float(pulse.get("life", 0.0))))
                    col = float(pulse.get("col", 0.0))
                    row = float(pulse.get("row", 0.0))
                    cx = (col + 0.5) * cell
                    cy = (row + 0.5) * cell
                    radius = max(2.0, (3.5 + (9.0 * (1.0 - life))) * cell * 0.18)
                    tone = int(28 + (38 * life))
                    outline = f"#{tone:02x}{min(120, tone + 22):02x}{min(150, tone + 40):02x}"
                    canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=outline, width=1, tags="pulse")
            if np is not None and self._work_ca_grid is not None:
                render_grid = getattr(self, "_work_render_grid", None)
                if render_grid is None:
                    render_grid = self._work_ca_grid.astype("float32")
                alive_cells = np.argwhere(render_grid > 0.02)
                if alive_cells.size > 0:
                    canvas.delete("branch")
                    cell_mid = cell * 0.5
                    alive_mask = render_grid > 0.02
                    dir_row = getattr(self, "_work_branch_dir_row", None)
                    dir_col = getattr(self, "_work_branch_dir_col", None)
                    junctions: list[tuple[int, int, float, float]] = []
                    for row, col in alive_cells.tolist():
                        intensity = float(render_grid[row, col])
                        age = float(self._work_ca_age[row, col]) if self._work_ca_age is not None else 0.0
                        x0 = (float(col) * cell) + cell_mid
                        y0 = (float(row) * cell) + cell_mid
                        branch_tone = int(min(190, 52 + (age * 2.4) + (intensity * 38.0)))
                        branch_color = f"#1c{min(190, branch_tone):02x}{min(220, branch_tone + 18):02x}"
                        degree = 0
                        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                            nr = row + dr
                            nc = col + dc
                            if 0 <= nr < alive_mask.shape[0] and 0 <= nc < alive_mask.shape[1] and bool(alive_mask[nr, nc]):
                                x1 = (float(nc) * cell) + cell_mid
                                y1 = (float(nr) * cell) + cell_mid
                                width = 1 if cell <= 3 else max(1, int(round(cell * 0.22)))
                                canvas.create_line(x0, y0, x1, y1, fill=branch_color, width=width, tags="branch")
                                degree += 1
                        if degree == 0 and dir_row is not None and dir_col is not None:
                            stub_dx = float(dir_col[row, col]) * max(1.2, cell * 0.9)
                            stub_dy = float(dir_row[row, col]) * max(1.2, cell * 0.9)
                            canvas.create_line(
                                x0 - stub_dx,
                                y0 - stub_dy,
                                x0 + stub_dx,
                                y0 + stub_dy,
                                fill=branch_color,
                                width=1 if cell <= 3 else max(1, int(round(cell * 0.18))),
                                tags="branch",
                            )
                        if getattr(self, "_work_junction_glow", True) and degree >= 3:
                            junctions.append((row, col, age, intensity))
                    if getattr(self, "_work_junction_glow", True):
                        for row, col, age, intensity in junctions:
                            x0 = int(col) * cell
                            y0 = int(row) * cell
                            x1 = x0 + cell
                            y1 = y0 + cell
                            radius = max(float(cell) * 0.4, min(float(cell) * 1.4, (float(cell) * 0.32) + (float(age) * 0.02)))
                            cool = int(min(150, 46 + (age * 0.65) + (intensity * 28.0)))
                            outline = f"#1a{min(150, cool):02x}{min(180, cool + 12):02x}"
                            canvas.create_oval(
                                ((x0 + x1) / 2.0) - radius,
                                ((y0 + y1) / 2.0) - radius,
                                ((x0 + x1) / 2.0) + radius,
                                ((y0 + y1) / 2.0) + radius,
                                outline=outline,
                                width=1,
                                tags="junction",
                            )
                for row, col in alive_cells.tolist():
                    x0 = int(col) * cell
                    y0 = int(row) * cell
                    x1 = x0 + cell
                    y1 = y0 + cell
                    age = float(self._work_ca_age[row, col]) if self._work_ca_age is not None else 0.0
                    intensity = float(render_grid[row, col])
                    alpha = max(0.08, min(1.0, 0.18 + (age * 0.05) + (intensity * 0.35)))
                    green = int(115 + (85 * alpha))
                    blue = int(150 + (75 * alpha))
                    fill = f"#84{green:02x}{blue:02x}"
                    if self._work_render_nodes:
                        if cell <= 2:
                            canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="", tags="cell")
                        else:
                            pad = max(0.0, cell * 0.34)
                            canvas.create_oval(x0 + pad, y0 + pad, x1 - pad, y1 - pad, fill=fill, outline="", tags="cell")
            root.update_idletasks()
            root.update()
        except Exception as exc:
            self.log.log("software_backend_render_failed", error=str(exc))
            self._teardown_gpu_backend()

    def draw_overlay(self) -> None:
        # Headless runtime does not use a separate overlay pass.
        return

    def dream_cycle(self) -> dict[str, Any]:
        ts = utc_now_iso()
        if self.novelty_seed_source == "hardware":
            seed = self._hardware_seed_value(
                {
                    "gpu_temp": self.signals.gpu_temp,
                    "gpu_util": self.signals.gpu_util,
                    "gpu_vram_used_mb": self.signals.gpu_vram_used_mb,
                    "fan_gpu": self.signals.fan_speed,
                    "disk_io": self.signals.disk_io,
                    "network_throughput": 0.0,
                },
                time.time(),
            )
            rng = random.Random(seed)
        else:
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
            "novelty_seed_source": self.novelty_seed_source,
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
        mirror = getattr(self, "mirror_state", MirrorState())
        ecosystem = dict(getattr(self, "ecosystem_state", {}) or {})
        payload = {
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
            "bloom_threshold": round(float(self.bloom_threshold), 4),
            "bloom_knee": round(float(self.bloom_knee), 4),
            "hdr_clamp": round(float(self.hdr_clamp), 3),
            "hdr_clamp_max": round(float(self.hdr_clamp), 3),
            "contrast": round(float(self.effective_contrast), 3),
            "saturation": round(float(self.effective_saturation), 3),
            "white_balance": [round(float(v), 4) for v in self.white_balance],
            "palette_mode": self.palette_mode,
            "active_preset": self.active_preset,
            "work_mode_enabled": bool(self.work_mode_enabled),
            "mirror_mode": ("work_mode_consciousness_mirror" if self.work_mode_enabled else "fishtank"),
            "layer_weight_particles": round(float(self.layer_weight_particles), 4),
            "layer_weight_rd": round(float(self.layer_weight_rd), 4),
            "layer_weight_volume": round(float(self.layer_weight_volume), 4),
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
            "gamma": 2.2,
            "tonemap_mode": self.tonemap_mode,
            "vol_luminance_mean": round(float(self.vol_luminance_mean), 5),
            "luminance_mean": round(float(self.luminance_mean), 5),
            "luminance_max": round(float(self.luminance_max), 5),
            "clipped_fraction_est": round(float(self.clipped_fraction_est), 5),
            "motion_scalar": round(float(self._motion_scalar), 5),
            "load_shed_active": bool(self.load_shed_active),
            "shed_reason": self.shed_reason,
            "lease_mode": self.lease_mode,
            "inference_quiesced": bool(self.inference_quiesced),
            "idle_mode_enabled": bool(self.idle_mode_enabled),
            "idle_trigger_source": self.idle_trigger_source,
            "idle_triggered_at": self.idle_triggered_at,
            "display_mode_active": bool(self.display_mode_active),
            "window_visible": bool(
                self.display_mode_active
                and (
                    (self.backend == "tk-work-window" and self._software_window is not None)
                    or (self.gpu_mode and self._window is not None and not self.headless)
                )
            ),
            "display_attached": bool(
                self.display_mode_active
                and (
                    (self.backend == "tk-work-window" and self._software_window is not None)
                    or (self.gpu_mode and self._window is not None and not self.headless)
                )
            ),
            "idle_inhibit_enabled": bool(self.idle_inhibit_enabled),
            "display_inhibitor_active": bool(self.display_inhibitor_active),
            "inhibitor_backend": self.inhibitor_backend,
            "features": self.features,
            "features_masked": list(self.features_masked),
            "novelty_seed_source": self.novelty_seed_source,
            "identity_profile": self.identity_profile,
            "activity_signal": round(float(self.activity_signal), 6),
            "agent_activity_level": round(float(self.agent_activity_level), 6),
            "agent_count_active": int(self.agent_count_active),
            "coordination_density": round(float(self.coordination_density), 6),
            "routing_activity": round(float(self.routing_activity), 6),
            "interaction_activity": round(float(self.interaction_activity), 6),
            "memory_activity": round(float(self.memory_activity), 6),
            "heavy_inference_suppressed": bool(self.heavy_inference_suppressed),
            "semantic_activity_source_summary": self.semantic_activity_source_summary,
            "mirror_state": {
                "baseline": round(float(mirror.baseline), 6),
                "reasoning": round(float(mirror.reasoning), 6),
                "insight": round(float(mirror.insight), 6),
                "learning": round(float(mirror.learning), 6),
                "attention": round(float(mirror.attention), 6),
                "overload": round(float(mirror.overload), 6),
                "coherence": round(float(mirror.coherence), 6),
                "reflection_phase": round(float(mirror.reflection_phase), 6),
                "collapse_risk": round(float(mirror.collapse_risk), 6),
                "repair_progress": round(float(mirror.repair_progress), 6),
            },
            "mirror_state_inference": dict(getattr(self, "mirror_state_inference", {}) or {}),
            "cadence_phase": dict(getattr(self, "cadence_phase", {}) or {}),
            "cadence_modulation": dict(getattr(self, "cadence_modulation", {}) or {}),
            "motif_activation": dict(getattr(self, "motif_activation", {}) or {}),
            "novel_layer_activation": dict(getattr(self, "novel_layer_activation", {}) or {}),
            "state_hue_mix": dict(getattr(self, "state_hue_mix", {}) or {}),
            "ecosystem_state": ecosystem,
            "scene_attractors": dict(getattr(self, "scene_attractors", {}) or {}),
            "wild_layer_activation": dict(getattr(self, "wild_layer_activation", {}) or {}),
            "colony_memory_state": dict(getattr(self, "colony_memory_state", {}) or {}),
            "colony_memory_level": round(float(getattr(self, "colony_memory_state", {}).get("colony_memory_level", 0.0) or 0.0), 6),
            "route_reinforcement": round(float(getattr(self, "colony_memory_state", {}).get("route_reinforcement", 0.0) or 0.0), 6),
            "dormant_zone_ratio": round(float(getattr(self, "colony_memory_state", {}).get("dormant_zone_ratio", 0.0) or 0.0), 6),
            "scar_tissue_intensity": round(float(getattr(self, "colony_memory_state", {}).get("scar_tissue_intensity", 0.0) or 0.0), 6),
            "repair_zone_intensity": round(float(getattr(self, "colony_memory_state", {}).get("repair_zone_intensity", 0.0) or 0.0), 6),
            "stabilized_habitat_ratio": round(float(getattr(self, "colony_memory_state", {}).get("stabilized_habitat_ratio", 0.0) or 0.0), 6),
            "ecological_persistence": round(float(getattr(self, "colony_memory_state", {}).get("ecological_persistence", 0.0) or 0.0), 6),
            "memory_flux": round(float(getattr(self, "colony_memory_state", {}).get("memory_flux", 0.0) or 0.0), 6),
            "collapse_risk": round(float(mirror.collapse_risk), 6),
            "repair_progress": round(float(mirror.repair_progress), 6),
            "collapse_visual_intensity": round(float(getattr(self, "collapse_visual_intensity", 0.0) or 0.0), 6),
            "repair_visual_intensity": round(float(getattr(self, "repair_visual_intensity", 0.0) or 0.0), 6),
        }
        if self.work_mode_enabled:
            therapeutic_state = getattr(self, "_therapeutic_scene_state", {})
            therapeutic_state = therapeutic_state if isinstance(therapeutic_state, dict) else {}
            fantasy_state = getattr(self, "_fantasy_scene_state", {})
            fantasy_state = fantasy_state if isinstance(fantasy_state, dict) else {}
            payload["cellular_automata"] = {
                "grid_width": int(self._work_grid_shape[1]),
                "grid_height": int(self._work_grid_shape[0]),
                "tick": int(getattr(self, "_work_ca_tick", 0)),
                "alive_cells": int(int(self._work_ca_grid.sum()) if np is not None else 0),
                "growth_memory": round(float(getattr(self, "_work_growth_memory", 0.0) or 0.0), 6),
                "growth_samples": int(getattr(self, "_work_growth_samples", 0) or 0),
                "growth_last_gain": round(float(getattr(self, "_work_growth_last_gain", 0.0) or 0.0), 6),
                "gpu_util_ema": round(float(getattr(self, "_work_gpu_util_ema", 0.0) or 0.0), 6),
                "preview_rows": self._work_mode_preview_rows(),
            }
            payload["work_scene"] = {
                "name": str(getattr(self, "_work_scene", "cellular_automata") or "cellular_automata"),
                "time_scale": round(float(getattr(self, "_work_scene_time_scale", 0.28) or 0.28), 6),
                "firefly_count": int(len(fantasy_state.get("fireflies", []))),
                "cloud_count": int(len(fantasy_state.get("clouds", []))),
                "mist_band_count": int(len(fantasy_state.get("mist_bands", []))),
                "duck_count": int(len(fantasy_state.get("ducks", []))),
                "fish_count": int(len(fantasy_state.get("fish", []))),
                "dragon_count": int(1 if isinstance(fantasy_state.get("dragon"), dict) and fantasy_state.get("dragon") else 0),
                "ambient_star_count": int(len(therapeutic_state.get("stars", []))),
                "ribbon_count": int(len(therapeutic_state.get("ribbons", []))),
                "grounding_cue_count": int(len(therapeutic_state.get("grounding_cues", []))),
                "current_cue": str(therapeutic_state.get("current_cue", "") or ""),
                "current_phase": str(therapeutic_state.get("current_phase", "") or ""),
                "current_direction": str(therapeutic_state.get("current_direction", "") or ""),
                "current_breath": str(therapeutic_state.get("current_breath", "") or ""),
                "breath_elapsed_seconds": round(float(therapeutic_state.get("breath_elapsed_seconds", 0.0) or 0.0), 3),
                "breath_phase_progress": round(float(therapeutic_state.get("breath_phase_progress", 0.0) or 0.0), 6),
                "text_enabled": bool(therapeutic_state.get("text_enabled", False)),
                "cue_text_visible": bool(therapeutic_state.get("cue_text_visible", False)),
                "footer_text_visible": bool(therapeutic_state.get("footer_text_visible", False)),
                "breath_label_visible": bool(therapeutic_state.get("breath_label_visible", False)),
                "breath_caption_visible": bool(therapeutic_state.get("breath_caption_visible", False)),
                "ring_radius_px": round(float(therapeutic_state.get("ring_radius_px", 0.0) or 0.0), 3),
                "drift_x_px": round(float(therapeutic_state.get("drift_x_px", 0.0) or 0.0), 3),
                "drift_y_px": round(float(therapeutic_state.get("drift_y_px", 0.0) or 0.0), 3),
                "grounding_enabled": bool(getattr(self, "_therapeutic_grounding_enabled", True)),
                "inhale_seconds": round(float(getattr(self, "_therapeutic_inhale_seconds", 4.0) or 4.0), 6),
                "hold_seconds": round(float(getattr(self, "_therapeutic_hold_seconds", 2.0) or 2.0), 6),
                "exhale_seconds": round(float(getattr(self, "_therapeutic_exhale_seconds", 5.0) or 5.0), 6),
                "sweep_seconds": round(float(getattr(self, "_therapeutic_sweep_seconds", 7.5) or 7.5), 6),
                "settle_seconds": round(float(getattr(self, "_therapeutic_settle_seconds", 4.0) or 4.0), 6),
                "breath_seconds": round(float(getattr(self, "_therapeutic_breath_seconds", 11.0) or 11.0), 6),
                "drift_seconds": round(float(getattr(self, "_therapeutic_drift_seconds", 180.0) or 180.0), 6),
                "drift_ratio": round(float(getattr(self, "_therapeutic_drift_ratio", 0.01) or 0.01), 6),
                "text_timeout_seconds": round(float(getattr(self, "_therapeutic_text_timeout_s", 60.0) or 60.0), 6),
            }
        for key, value in ecosystem.items():
            if isinstance(value, (int, float)):
                payload[key] = round(float(value), 6) if not isinstance(value, int) else int(value)
            else:
                payload[key] = value
        return payload

    def persist_state(self) -> dict[str, Any]:
        payload = self.capture_state()
        payload["frame"] = self.frame_index
        atomic_write_json(self.output_path, payload)
        return payload

    def tick(self) -> dict[str, Any]:
        self.update_state()
        if self.work_mode_enabled:
            self._update_work_mode_render_grid()
        self.render_scene()
        self.draw_overlay()
        return self.persist_state()

    def close(self) -> None:
        self._teardown_gpu_backend()
