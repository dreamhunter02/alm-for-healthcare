from datetime import date
from decimal import Decimal

from healthcare_alm.models import RetirementRequest
from healthcare_alm.orchestrator.graph import run_workflow
from healthcare_alm.orchestrator.state import WorkflowServices

EXPECTED_STAGES = [
    "maude_ingestion",
    "correlation",
    "risk_scoring",
    "regulatory_grounding",
    "retirement_planning",
    "audit_reporting",
    "verification",
]


def test_cached_workflow_runs_all_seven_stages(tmp_path):
    services = WorkflowServices.cached(output_dir=tmp_path, as_of_date=date(2026, 8, 15))
    request = RetirementRequest(budget=Decimal("120000"), output_dir=tmp_path)

    result = run_workflow(request, services)

    assert result.status == "completed"
    assert [event.stage for event in result.stage_events] == EXPECTED_STAGES
    assert all(event.status == "completed" for event in result.stage_events)
    assert len(result.plan.items) == 12
    assert result.trace_id
    assert result.sandbox_provider == "local_subprocess"
    assert result.artifacts
    assert all(artifact.path.exists() for artifact in result.artifacts)


def test_workflow_keeps_public_evidence_at_model_or_product_level(tmp_path):
    services = WorkflowServices.cached(output_dir=tmp_path, as_of_date=date(2026, 8, 15))

    result = run_workflow(RetirementRequest(output_dir=tmp_path), services)

    assert all(evidence.unit_attribution is False for evidence in result.evidence)
    assert all(evidence.source_urls for evidence in result.evidence)


def test_cached_demo_contains_decisive_retire_and_maintain_examples(tmp_path):
    services = WorkflowServices.cached(output_dir=tmp_path, as_of_date=date(2026, 8, 15))

    result = run_workflow(RetirementRequest(output_dir=tmp_path), services)

    actions = {score.action for score in result.scores}
    assert {"retire", "maintain"} <= actions
