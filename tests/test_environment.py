import os

import pytest

from healthcare_alm.environment import EnvironmentConfigError, load_workshop_environment, run_env_command


def _write_env(path, **values):
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))


def test_load_workshop_environment_reads_participant_configuration(tmp_path):
    env_file = tmp_path / ".env"
    _write_env(
        env_file,
        NVIDIA_API_KEY="participant-secret",
        NVIDIA_API_BASE_URL="https://llm.example.test/v1",
        NVIDIA_MODEL_NAME="provider/test-model",
    )

    environment = load_workshop_environment(env_file, base_environment={"PATH": "/bin"})

    assert environment["NVIDIA_API_KEY"] == "participant-secret"
    assert environment["NVIDIA_API_BASE_URL"] == "https://llm.example.test/v1"
    assert environment["NVIDIA_MODEL_NAME"] == "provider/test-model"
    assert environment["PATH"] == "/bin"


def test_process_environment_overrides_env_file(tmp_path):
    env_file = tmp_path / ".env"
    _write_env(
        env_file,
        NVIDIA_API_KEY="file-secret",
        NVIDIA_API_BASE_URL="https://file.example.test/v1",
        NVIDIA_MODEL_NAME="file/model",
    )

    environment = load_workshop_environment(
        env_file,
        base_environment={
            "NVIDIA_API_KEY": "process-secret",
            "NVIDIA_API_BASE_URL": "https://process.example.test/v1",
            "NVIDIA_MODEL_NAME": "process/model",
        },
    )

    assert environment["NVIDIA_API_KEY"] == "process-secret"
    assert environment["NVIDIA_API_BASE_URL"] == "https://process.example.test/v1"
    assert environment["NVIDIA_MODEL_NAME"] == "process/model"


def test_missing_participant_configuration_has_actionable_error(tmp_path):
    with pytest.raises(EnvironmentConfigError, match=r"copy \.env\.example to \.env"):
        load_workshop_environment(tmp_path / ".env", base_environment={})


def test_run_env_command_limits_secret_to_child_environment(tmp_path):
    env_file = tmp_path / ".env"
    _write_env(
        env_file,
        NVIDIA_API_KEY="child-only-secret",
        NVIDIA_API_BASE_URL="https://llm.example.test/v1",
        NVIDIA_MODEL_NAME="provider/test-model",
    )
    captured = {}

    def executor(program, command, environment):
        captured.update(program=program, command=command, environment=environment)
        return 17

    original = os.environ.get("NVIDIA_API_KEY")
    result = run_env_command(
        ["nat", "run", "--input", "question"],
        env_file=env_file,
        executor=executor,
        base_environment={"PATH": "/bin"},
    )

    assert result == 17
    assert captured["program"] == "nat"
    assert captured["environment"]["NVIDIA_API_KEY"] == "child-only-secret"
    assert captured["command"] == ["nat", "run", "--input", "question"]
    assert os.environ.get("NVIDIA_API_KEY") == original
