"""Configuration: execution limits and model names.

Limits are configurable (A-level requirement). Model names are NEVER hard-coded:
they come from environment variables so different Gemini models can be compared.
The API key is read from the environment and is never stored in the repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # optional: load .env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


@dataclass(frozen=True)
class AgentConfig:
    max_steps: int = 10
    max_tool_calls: int = 20
    max_retries: int = 2
    max_tokens: int = 20000
    model_planner: str = ""  # stronger model: planning and final study plan
    model_fast: str = ""  # cheaper model: routine tool-selection steps

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls(
            max_steps=_int_env("MAX_STEPS", 10),
            max_tool_calls=_int_env("MAX_TOOL_CALLS", 20),
            max_retries=_int_env("MAX_RETRIES", 2),
            max_tokens=_int_env("MAX_TOKENS", 20000),
            model_planner=os.environ.get("GEMINI_MODEL_PLANNER", ""),
            model_fast=os.environ.get("GEMINI_MODEL_FAST", ""),
        )


def get_api_key() -> str:
    """Return the Gemini API key from the environment or raise a clear error."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return key
