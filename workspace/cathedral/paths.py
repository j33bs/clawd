from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT / "workspace"
RUNTIME_ROOT = WORKSPACE_ROOT / "runtime"
RUNTIME_MIRROR_ROOT = REPO_ROOT / "runtime"
RUNTIME_LOGS = RUNTIME_ROOT / "logs"
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
NOVELTY_ARCHIVE_DIR = MEMORY_ROOT / "novelty_archive"
AESTHETIC_EVENTS_DIR = MEMORY_ROOT / "aesthetic_events"
DREAM_STATES_DIR = MEMORY_ROOT / "dream_states"

SYSTEM_PHYSIOLOGY_PATH = RUNTIME_ROOT / "system_physiology.json"
TACTI_STATE_PATH = RUNTIME_ROOT / "tacti_state.json"
CURIOSITY_LATEST_PATH = RUNTIME_ROOT / "curiosity_latest.json"
FISHTANK_STATE_PATH = RUNTIME_ROOT / "fishtank_state.json"
FISHTANK_CONTROL_STATE_PATH = RUNTIME_ROOT / "fishtank_control_state.json"
PHASE_ONE_IDLE_STATUS_PATH = RUNTIME_ROOT / "phase1_idle_status.json"
FISHTANK_CAPTURE_REQUEST_PATH = RUNTIME_ROOT / "fishtank_capture_request.json"
FISHTANK_COLONY_MEMORY_STATE_PATH = RUNTIME_ROOT / "fishtank_colony_memory_state.json"
FISHTANK_COLONY_MEMORY_LAYERS_PATH = RUNTIME_ROOT / "fishtank_colony_memory_layers.npz"
GPU_LEASE_PATH = RUNTIME_ROOT / "gpu_lease.json"
TELEGRAM_STATE_PATH = RUNTIME_ROOT / "telegram_state.json"
TELEGRAM_POLL_LOCK_PATH = RUNTIME_ROOT / "telegram_poll.lock"
UE5_PACKAGED_ROOT = WORKSPACE_ROOT / "audit" / "_evidence" / "ue5_packaged" / "Linux"
UE5_PACKAGED_LAUNCHER = UE5_PACKAGED_ROOT / "DaliMirror.sh"

SYSTEM_PHYSIOLOGY_MIRROR_PATH = RUNTIME_MIRROR_ROOT / "system_physiology.json"
TACTI_STATE_MIRROR_PATH = RUNTIME_MIRROR_ROOT / "tacti_state.json"


def ensure_runtime_dirs() -> None:
    for directory in (
        RUNTIME_ROOT,
        RUNTIME_MIRROR_ROOT,
        RUNTIME_LOGS,
        MEMORY_ROOT,
        NOVELTY_ARCHIVE_DIR,
        AESTHETIC_EVENTS_DIR,
        DREAM_STATES_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
