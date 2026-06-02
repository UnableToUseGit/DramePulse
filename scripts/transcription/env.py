from __future__ import annotations

import os
from pathlib import Path


def clean_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_dotenv_values(env_path: Path | None = None) -> dict[str, str]:
    if env_path is None or not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = clean_env_value(value)
    return values


def get_env_value(key: str, *, env_path: Path | None = None) -> str | None:
    dotenv_values = load_dotenv_values(env_path)
    value = dotenv_values.get(key)
    if value is not None:
        value = value.strip()
        if value:
            return value

    value = os.environ.get(key)
    if value is not None:
        value = value.strip()
        return value or None
    return None
