"""
DEPRECATED: compatibility forwarder.
Canonical source is workspace/tacti/arousal_oscillator.py.
"""

from importlib.util import spec_from_file_location
from pathlib import Path

_shim_file = Path(__file__).resolve()
_src = _shim_file.parents[1] / "tacti" / "arousal_oscillator.py"
__file__ = str(_src)
if not globals().get("__package__"):
    __package__ = __name__.rpartition(".")[0]
if globals().get("__spec__") is None:
    __spec__ = spec_from_file_location(__name__, str(_src))
if not globals().get("_TACTI_SHIM_EXECUTED", False):
    _code = _src.read_text(encoding="utf-8")
    exec(compile(_code, str(_src), "exec"), globals(), globals())
    globals()["_TACTI_SHIM_EXECUTED"] = True
if "__all__" in globals():
    __all__ = list(__all__)
