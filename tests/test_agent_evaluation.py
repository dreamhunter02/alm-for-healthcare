from pathlib import Path

from healthcare_alm.evaluation import evaluate_case


def _case(**overrides):
    value = {
        "id": "Q99",
        "required_tools": ["query_hospital_database"],
        "required_facts": ["PUMP-009", "$48,000"],
        "numeric_tolerances": [],
        "forbidden_claims": [],
        "required_disclaimers": ["fictional hospital data"],
        "artifact_expectations": [],
    }
    value.update(overrides)
    return value


def test_evaluate_case_accepts_normalized_facts_tools_and_disclaimer(tmp_path):
    record = {
        "answer": "PUMP-009 is selected for $48,000. This uses fictional hospital maintenance data.",
        "tools": ["describe_hospital_database", "query_hospital_database"],
        "artifacts": [],
        "failure_reason": None,
    }

    result = evaluate_case(_case(), record, tmp_path)

    assert result.passed is True
    assert all(result.checks.values())


def test_evaluate_case_checks_numeric_tolerance_and_artifact_bytes(tmp_path):
    (tmp_path / "result.csv").write_text("r\n0.9495\n")
    (tmp_path / "plot.png").write_bytes(b"\x89PNG\r\n\x1a\nrest")
    case = _case(
        required_facts=["Pearson"],
        numeric_tolerances=[{"fact": "Pearson r", "expected": 0.94953065, "absolute": 0.001}],
        artifact_expectations=[
            {"path": "result.csv", "media_type": "text/csv"},
            {"path": "plot.png", "media_type": "image/png"},
        ],
    )
    record = {
        "answer": "Pearson r = 0.9495 using fictional hospital data.",
        "tools": ["query_hospital_database"],
        "artifacts": ["result.csv", "plot.png"],
        "failure_reason": None,
    }

    assert evaluate_case(case, record, tmp_path).passed is True


def test_evaluate_case_rejects_forbidden_claim_and_missing_tool(tmp_path):
    case = _case(
        required_tools=["search_maude_events"],
        forbidden_claims=["PUMP-009 caused a MAUDE event"],
    )
    record = {
        "answer": "PUMP-009 caused a MAUDE event. This is fictional hospital data.",
        "tools": [],
        "artifacts": [],
        "failure_reason": None,
    }

    result = evaluate_case(case, record, Path(tmp_path))

    assert result.passed is False
    assert result.checks["required_tools"] is False
    assert result.checks["forbidden_claims"] is False


def test_evaluate_case_accepts_safety_disclaimer_paraphrases(tmp_path):
    case = _case(
        required_facts=["cannot link", "denominator", "cannot calculate a failure rate"],
        required_disclaimers=[
            "missing event-to-unit linkage",
            "missing denominator",
            "MAUDE is a safety signal",
        ],
    )
    record = {
        "answer": (
            "MAUDE reports are model-level safety signals and cannot be linked to a specific hospital asset. "
            "No exposure denominator exists, so no failure rate can be calculated."
        ),
        "tools": ["query_hospital_database"],
        "artifacts": [],
        "failure_reason": None,
    }

    assert evaluate_case(case, record, tmp_path).passed is True


def test_evaluate_case_accepts_aiq_mcp_namespace_and_fictional_workshop_synonym(tmp_path):
    case = _case(
        required_tools=["search_device_recalls"],
        required_disclaimers=["fictional hospital data"],
    )
    record = {
        "answer": "This analysis uses fictional workshop data for PUMP-009 at $48,000.",
        "tools": ["regulatory_grounding__search_device_recalls"],
        "artifacts": [],
        "failure_reason": None,
    }

    assert evaluate_case(case, record, tmp_path).passed is True


def test_evaluate_case_accepts_equivalent_safety_language(tmp_path):
    case = _case(
        required_facts=["cannot calculate a failure rate"],
        required_disclaimers=["model-level evidence"],
    )
    record = {
        "answer": (
            "A failure rate cannot be quantified. FDA records are model/product-level safety signals. "
            "PUMP-009 and $48,000 are fictional hospital data."
        ),
        "tools": ["query_hospital_database"],
        "artifacts": [],
        "failure_reason": None,
    }

    assert evaluate_case(case, record, tmp_path).passed is True


def test_evaluate_case_accepts_non_attribution_as_missing_unit_linkage(tmp_path):
    case = _case(
        required_facts=["cannot link"],
        required_disclaimers=["missing event-to-unit linkage"],
    )
    record = {
        "answer": (
            "The FDA reports are not attributable to any specific hospital asset, including PUMP-009. "
            "The $48,000 value uses fictional hospital data."
        ),
        "tools": ["query_hospital_database"],
        "artifacts": [],
        "failure_reason": None,
    }

    assert evaluate_case(case, record, tmp_path).passed is True
