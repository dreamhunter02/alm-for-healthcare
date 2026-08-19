from pathlib import Path

import pytest
import yaml

EXPECTED_STAGES = [
    "maude_ingestion",
    "correlation",
    "risk_scoring",
    "regulatory_grounding",
    "retirement_planning",
    "audit_reporting",
    "verification",
]


def test_workshop_config_declares_seven_stage_contract():
    config = yaml.safe_load(Path("configs/workshop.yml").read_text())

    assert config["workflow"]["stages"] == EXPECTED_STAGES
    assert config["defaults"]["product_code"] == "FRN"


def test_aiq_config_registers_single_deep_agent_and_healthcare_tools():
    config = yaml.safe_load(Path("configs/config_aiq_agent.yml").read_text())

    assert config["workflow"]["_type"] == "healthcare_alm_deep_agent"
    assert config["workflow"]["llm"] == "nemotron_ultra"
    assert config["workflow"]["sandbox"] == "agent_sandbox"
    assert set(config["functions"]) >= {
        "describe_hospital_database",
        "query_hospital_database",
        "search_maude_events",
        "score_retirement_risk",
        "build_replacement_plan",
        "agent_sandbox",
    }
    assert config["function_groups"]["regulatory_grounding"]["_type"] == "mcp_client"
    assert config["llms"]["nemotron_ultra"]["api_key"] == "${NVIDIA_API_KEY}"
    assert config["llms"]["nemotron_ultra"]["base_url"] == "${NVIDIA_API_BASE_URL}"
    assert config["llms"]["nemotron_ultra"]["model_name"] == "${NVIDIA_MODEL_NAME}"


def test_aiq_plugin_registers_deep_agent_when_runtime_is_installed():
    from healthcare_alm.aiq.register import AIQ_AVAILABLE, HealthcareALMDeepAgentConfig

    assert AIQ_AVAILABLE is True
    assert HealthcareALMDeepAgentConfig.__name__ == "HealthcareALMDeepAgentConfig"


@pytest.mark.asyncio
async def test_describe_database_tool_satisfies_nat_single_input_contract():
    from healthcare_alm.aiq.register import DescribeHospitalDatabaseConfig, describe_database_tool

    generator = describe_database_tool.__wrapped__(DescribeHospitalDatabaseConfig(), object())
    function_info = await anext(generator)

    assert function_info is not None
