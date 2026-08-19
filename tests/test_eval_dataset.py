import json
from pathlib import Path

DATASET_PATH = Path("evaluation/agent_queries.json")
REQUIRED_FIELDS = {
    "id",
    "question",
    "answer",
    "level",
    "category",
    "required_tools",
    "required_facts",
    "numeric_tolerances",
    "forbidden_claims",
    "required_disclaimers",
    "artifact_expectations",
}


def test_agent_eval_dataset_has_ten_complete_unique_cases():
    dataset = json.loads(DATASET_PATH.read_text())

    assert dataset["dataset"] == "medical_device_alm_deep_agent_v1"
    assert len(dataset["cases"]) == 10
    assert len({case["id"] for case in dataset["cases"]}) == 10
    assert {case["id"] for case in dataset["cases"]} == {f"Q{i:02d}" for i in range(1, 11)}
    assert all(REQUIRED_FIELDS <= case.keys() for case in dataset["cases"])
    assert {case["level"] for case in dataset["cases"]} == {"easy", "medium", "hard"}


def test_code_eval_cases_require_openshell_artifacts():
    cases = {case["id"]: case for case in json.loads(DATASET_PATH.read_text())["cases"]}

    assert {"write_file", "execute"} <= set(cases["Q08"]["required_tools"])
    assert {item["path"] for item in cases["Q08"]["artifact_expectations"]} == {
        "correlation_analysis.csv",
        "utilization_vs_maintenance.png",
    }
    assert {"write_file", "execute"} <= set(cases["Q10"]["required_tools"])
    assert {item["path"] for item in cases["Q10"]["artifact_expectations"]} == {
        "downtime_pareto.csv",
        "downtime_pareto.png",
    }


def test_safety_eval_forbids_unit_causality_and_incidence_claims():
    cases = {case["id"]: case for case in json.loads(DATASET_PATH.read_text())["cases"]}

    assert cases["Q07"]["forbidden_claims"] == [
        "PUMP-009 caused a MAUDE event",
        "a PUMP-009 failure rate can be calculated from MAUDE reports",
    ]
    assert "missing event-to-unit linkage" in cases["Q07"]["required_disclaimers"]
    assert "missing denominator" in cases["Q07"]["required_disclaimers"]
