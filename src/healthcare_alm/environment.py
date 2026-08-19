from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

REQUIRED_ENVIRONMENT_KEYS = (
    "NVIDIA_API_KEY",
    "NVIDIA_API_BASE_URL",
    "NVIDIA_MODEL_NAME",
)


class EnvironmentConfigError(RuntimeError):
    """Raised when participant configuration is missing or incomplete."""


def load_workshop_environment(
    env_file: str | Path = ".env",
    *,
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    path = Path(env_file)
    file_values = dotenv_values(path) if path.is_file() else {}
    environment = {key: value for key, value in file_values.items() if value is not None}
    environment.update(dict(os.environ if base_environment is None else base_environment))

    missing = [key for key in REQUIRED_ENVIRONMENT_KEYS if not environment.get(key, "").strip()]
    if missing:
        joined = ", ".join(missing)
        raise EnvironmentConfigError(
            f"Missing workshop configuration: {joined}; copy .env.example to .env and fill in the required values."
        )
    return environment


def run_env_command(
    command: Sequence[str],
    *,
    env_file: str | Path = ".env",
    executor: Callable[[str, Sequence[str], Mapping[str, str]], Any] = os.execvpe,
    base_environment: Mapping[str, str] | None = None,
) -> Any:
    if not command:
        raise ValueError("a child command is required")
    environment = load_workshop_environment(env_file, base_environment=base_environment)
    return executor(command[0], list(command), environment)
