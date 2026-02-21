"""
DEPRECATED: compatibility forwarder.
Canonical source is workspace/tacti/dream_consolidation.py.
"""

from importlib.util import spec_from_file_location
from pathlib import Path

_shim_file = Path(__file__).resolve()
_src = _shim_file.parents[1] / "tacti" / "dream_consolidation.py"
__file__ = str(_src)
if not globals().get("__package__"):
    __package__ = __name__.rpartition(".")[0]
if globals().get("__spec__") is None:
    __spec__ = spec_from_file_location(__name__, str(_src))
_code = _src.read_text(encoding="utf-8")
exec(compile(_code, str(_src), "exec"), globals(), globals())
if "__all__" in globals():
    __all__ = list(__all__)
