"""
DEPRECATED: compatibility forwarder.
Canonical source is workspace/tacti/prefetch.py.
"""

from pathlib import Path

_src = Path(__file__).resolve().parents[1] / "tacti" / "prefetch.py"
_code = _src.read_text(encoding="utf-8")
exec(compile(_code, str(_src), "exec"), globals(), globals())
