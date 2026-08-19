from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_open_webui_compose_uses_direct_aiq_connection_without_nvidia_credentials():
    compose = yaml.safe_load((ROOT / "compose.open-webui.yml").read_text())
    service = compose["services"]["open-webui"]
    environment = service["environment"]

    assert service["ports"] == ["127.0.0.1:3000:8080"]
    assert environment["WEBUI_AUTH"] == "false"
    assert environment["OPENAI_API_BASE_URLS"] == "http://host.docker.internal:8000/v1"
    assert '"model_ids":["healthcare-alm"]' in environment["OPENAI_API_CONFIGS"]
    assert "NVIDIA_API_KEY" not in environment


def test_open_webui_scripts_reference_query_driven_aiq_config():
    start = (ROOT / "scripts" / "start_open_webui.sh").read_text()

    assert "nat serve" in start
    assert "configs/config_aiq_agent.yml" in start
    assert "run_with_env.py" in start
    assert "compose.open-webui.yml" in start


def test_open_webui_start_script_owns_aiq_process_lifecycle():
    start = (ROOT / "scripts" / "start_open_webui.sh").read_text()

    assert 'wait "$aiq_pid"' in start
    assert "nohup" not in start
