from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from scripts.transcription.env import load_dotenv_values

from pipelines.client.openai_client import OpenAiLlmClient
from pipelines.client.volc_ark import VolcArkLlmClient


def _first_env_value(dotenv_values: dict[str, str], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = dotenv_values.get(key)
        if value:
            return value
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return None


def _llm_config_value(dotenv_values: dict[str, str], generic_key: str, legacy_keys: Sequence[str]) -> str | None:
    generic_value = _first_env_value(dotenv_values, [generic_key])
    if generic_value:
        return generic_value
    return _first_env_value(dotenv_values, legacy_keys)


def build_llm_client(*, env_path: Path | None = None):
    dotenv_values = load_dotenv_values(env_path)
    provider = (_first_env_value(dotenv_values, ["LLM_PROVIDER"]) or "ark").strip().lower()
    if provider in {"ark", "volc", "volc_ark", "volcark"}:
        return VolcArkLlmClient(
            api_key=_llm_config_value(dotenv_values, "API_KEY", ["ARK_API_KEY"]),
            base_url=_llm_config_value(dotenv_values, "BASE_URL", ["ARK_BASE_URL"]),
            model_name=_llm_config_value(dotenv_values, "MODEL", ["ARK_MODEL"]),
        )
    if provider in {"openai", "open_ai"}:
        return OpenAiLlmClient(
            api_key=_llm_config_value(dotenv_values, "API_KEY", ["OPENAI_API_KEY"]),
            base_url=_llm_config_value(dotenv_values, "BASE_URL", ["OPENAI_BASE_URL"]),
            model_name=_llm_config_value(dotenv_values, "MODEL", ["OPENAI_MODEL"]),
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def build_ark_client(*, env_path: Path | None = None):
    return build_llm_client(env_path=env_path)
