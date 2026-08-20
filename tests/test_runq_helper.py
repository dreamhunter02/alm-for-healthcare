import importlib.util
import json
from pathlib import Path

SCRIPT_PATH = Path("scripts/runq.py")
WRAPPER_PATH = Path("scripts/runq")


def _load_runq_module():
    assert SCRIPT_PATH.is_file(), "scripts/runq.py must provide the workshop query helper"
    spec = importlib.util.spec_from_file_location("runq_helper", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runq_resolves_eval_ids_and_preserves_literal_questions(tmp_path):
    runq = _load_runq_module()
    dataset = tmp_path / "agent_queries.json"
    dataset.write_text(json.dumps({"cases": [{"id": "Q09", "question": "Create the ICU retirement recommendation."}]}))

    assert runq.resolve_question("Q09", dataset) == "Create the ICU retirement recommendation."
    assert runq.resolve_question("How many ICU pumps are there?", dataset) == "How many ICU pumps are there?"


def test_runq_formats_authoritative_tool_and_artifact_trace():
    runq = _load_runq_module()

    result = runq.format_trace(
        {
            "tools": ["describe_hospital_database", "query_hospital_database", "execute"],
            "artifacts": ["correlation_analysis.csv", "utilization_vs_maintenance.png"],
        }
    )

    assert "describe_hospital_database" in result
    assert "query_hospital_database" in result
    assert "execute" in result
    assert "correlation_analysis.csv" in result
    assert "utilization_vs_maintenance.png" in result


def test_runq_has_an_executable_shell_entrypoint():
    assert WRAPPER_PATH.is_file()
    assert WRAPPER_PATH.stat().st_mode & 0o111
