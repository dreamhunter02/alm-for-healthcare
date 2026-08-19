from decimal import Decimal

import pytest

from healthcare_alm.agent.domain import MedicalDeviceTools


@pytest.fixture()
def tools(tmp_path):
    return MedicalDeviceTools(db_path=tmp_path / "healthcare_alm.db")


def test_database_tools_describe_and_query_fictional_inventory(tools):
    schema = tools.describe_hospital_database()
    result = tools.query_hospital_database(
        "SELECT asset_id FROM inventory WHERE department = 'ICU' ORDER BY asset_id"
    )

    assert "inventory" in schema["tables"]
    assert schema["data_classification"] == "fictional workshop data"
    assert result["row_count"] == 3
    assert [row["asset_id"] for row in result["rows"]] == ["PUMP-001", "PUMP-004", "PUMP-009"]


def test_database_tool_rejects_writes(tools):
    with pytest.raises(ValueError, match="Only SELECT"):
        tools.query_hospital_database("DELETE FROM inventory")


def test_database_tool_returns_recoverable_error_for_invalid_select(tools):
    result = tools.query_hospital_database("SELECT model FROM inventory")

    assert result["status"] == "query_error"
    assert "no such column" in result["error"]
    assert result["retry_guidance"] == "Inspect describe_hospital_database and retry with valid columns."


@pytest.mark.parametrize("table", ["recalls", "maude_events"])
def test_database_tool_routes_fda_tables_to_dedicated_tools(tools, table):
    result = tools.query_hospital_database(f"SELECT * FROM {table}")

    assert result["status"] == "query_error"
    assert "dedicated FDA tools" in result["retry_guidance"]


def test_maude_search_returns_signals_and_non_attribution_warning(tools):
    result = tools.search_maude_events(product_code="FRN", manufacturer="Zyno", model_number="Z-800")

    assert result["status"] == "available_matches"
    assert result["records"]
    assert all("source_url" in record for record in result["records"])
    assert "cannot be linked to a specific hospital asset" in result["safety_notice"]


def test_deterministic_score_tool_returns_reference_scores(tools):
    result = tools.score_retirement_risk()
    scores = {item["asset_id"]: item for item in result["scores"]}

    assert (scores["PUMP-009"]["total"], scores["PUMP-009"]["action"]) == (74, "retire")
    assert (scores["PUMP-004"]["total"], scores["PUMP-004"]["action"]) == (53, "plan_replacement")
    assert (scores["PUMP-007"]["total"], scores["PUMP-007"]["action"]) == (53, "plan_replacement")
    assert (scores["PUMP-005"]["total"], scores["PUMP-005"]["action"]) == (52, "plan_replacement")


def test_budget_plan_tool_uses_deterministic_scores(tools):
    result = tools.build_replacement_plan(annual_budget=Decimal("50000"))

    assert [item["asset_id"] for item in result["current_phase"]] == ["PUMP-009", "PUMP-004"]
    assert result["current_phase_spend"] == "48000"
    assert result["remaining_budget"] == "2000"
