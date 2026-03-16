from __future__ import annotations

import json
from pathlib import Path


def parse_env_text(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value[:1] in {'"', "'"} and value[-1:] == value[:1]:
            quote = value[:1]
            if quote == '"':
                value = json.loads(value)
            else:
                value = value[1:-1]
        result[key] = value
    return result


def load_env_file(path: Path) -> dict[str, str]:
    path = Path(path).expanduser()
    if not path.is_file():
        return {}
    return parse_env_text(path.read_text(encoding="utf-8"))


def _quote_env_value(value: str) -> str:
    text = str(value)
    if text and all(ch not in text for ch in ' \t\r\n#"\''):
        return text
    return json.dumps(text, ensure_ascii=True)


def write_env_file(path: Path, values: dict[str, str]) -> None:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={_quote_env_value(value)}" for key, value in values.items() if value is not None]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

