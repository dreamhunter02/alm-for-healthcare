from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from healthcare_alm.analysis.correlate import correlate_assets
from healthcare_alm.analysis.planner import build_retirement_plan
from healthcare_alm.data.setup_database import build_database, load_inventory, load_maintenance
from healthcare_alm.fda.normalize import normalize_maude
from healthcare_alm.models import (
    ArtifactRef,
    RetirementRequest,
    RiskScore,
    StageEvent,
    WorkflowResult,
)
from healthcare_alm.orchestrator.state import WorkflowServices, WorkflowState

STAGES = [
    "maude_ingestion",
    "correlation",
    "risk_scoring",
    "regulatory_grounding",
    "retirement_planning",
    "audit_reporting",
    "verification",
]


def _now() -> datetime:
    return datetime.now(UTC)


def _event(
    state: WorkflowState,
    stage: str,
    started_at: datetime,
    input_count: int,
    output_count: int,
    message: str,
) -> list[StageEvent]:
    return [
        *state.get("stage_events", []),
        StageEvent(
            stage=stage,
            status="completed",
            started_at=started_at,
            completed_at=_now(),
            input_count=input_count,
            output_count=output_count,
            trace_id=state["trace_id"],
            message=message,
        ),
    ]


def _score_evidence(state: WorkflowState, evidence_rows, folder: str) -> tuple[list[RiskScore], str]:
    scores = []
    provider = "unknown"
    for evidence in evidence_rows:
        output_dir = state["services"].output_dir / "sandbox" / folder / evidence.asset.asset_id
        result = state["services"].sandbox_runner.run_score(
            {"evidence": evidence.model_dump(mode="json"), "config": {}}, output_dir
        )
        if result.status != "completed" or not result.artifacts:
            raise RuntimeError(f"Sandbox scoring failed for {evidence.asset.asset_id}: {result.stderr}")
        provider = result.provider
        scores.append(RiskScore.model_validate_json(result.artifacts[0].path.read_text()))
    return scores, provider


def maude_ingestion(state: WorkflowState) -> dict:
    started = _now()
    request, services = state["request"], state["services"]
    response = services.fda_client.fetch_maude(request.product_code, live=request.live_fda)
    maude = normalize_maude(response.results, response.source_url)
    assets = load_inventory(services.inventory_path)
    maintenance = load_maintenance(services.maintenance_path)
    return {
        "maude_response": response,
        "maude": maude,
        "assets": assets,
        "maintenance": maintenance,
        "fda_provenance": {"maude": response.provenance},
        "stage_events": _event(
            state,
            "maude_ingestion",
            started,
            len(response.results),
            len(maude),
            f"Loaded {len(maude)} deduplicated MAUDE signals ({response.provenance}).",
        ),
    }


def correlation(state: WorkflowState) -> dict:
    started = _now()
    evidence = correlate_assets(state["assets"], state["maintenance"], state["maude"], [], state["services"].as_of_date)
    return {
        "evidence": evidence,
        "stage_events": _event(
            state,
            "correlation",
            started,
            len(state["assets"]),
            len(evidence),
            "Joined model/product-level FDA signals to fictional hospital inventory.",
        ),
    }


def risk_scoring(state: WorkflowState) -> dict:
    started = _now()
    scores, provider = _score_evidence(state, state["evidence"], "provisional")
    return {
        "scores": scores,
        "sandbox_provider": provider,
        "stage_events": _event(
            state,
            "risk_scoring",
            started,
            len(state["evidence"]),
            len(scores),
            f"Executed versioned scoring in {provider}.",
        ),
    }


def regulatory_grounding(state: WorkflowState) -> dict:
    started = _now()
    request, services = state["request"], state["services"]
    result = services.recall_service.search(request.product_code)
    warnings = list(state.get("warnings", []))
    recalls = result.records
    if result.status == "unavailable":
        warnings.append(result.message)
    evidence = correlate_assets(state["assets"], state["maintenance"], state["maude"], recalls, services.as_of_date)
    scores, provider = _score_evidence(state, evidence, "grounded")
    provenance = dict(state.get("fda_provenance", {}))
    provenance["recalls"] = result.provenance
    return {
        "recalls": recalls,
        "evidence": evidence,
        "scores": scores,
        "warnings": warnings,
        "sandbox_provider": provider,
        "fda_provenance": provenance,
        "stage_events": _event(
            state,
            "regulatory_grounding",
            started,
            1,
            len(recalls),
            f"Recall evidence status: {result.status}; recomputed grounded scores.",
        ),
    }


def retirement_planning(state: WorkflowState) -> dict:
    started = _now()
    plan = build_retirement_plan(state["scores"], state["request"].budget)
    return {
        "plan": plan,
        "stage_events": _event(
            state,
            "retirement_planning",
            started,
            len(state["scores"]),
            len(plan.items),
            f"Allocated ${plan.current_phase_spend} of ${plan.annual_budget} current budget.",
        ),
    }


def _write_artifact(path: Path, payload: dict) -> ArtifactRef:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True, default=str).encode()
    path.write_bytes(data)
    return ArtifactRef(
        artifact_id="workflow-audit-json",
        path=path,
        media_type="application/json",
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


def audit_reporting(state: WorkflowState) -> dict:
    started = _now()
    services = state["services"]
    build_database(
        services.output_dir / "healthcare_alm.db",
        state["assets"],
        state["maintenance"],
        state["maude"],
        state.get("recalls", []),
    )
    artifact = _write_artifact(
        services.output_dir / "audit" / "workflow_result.json",
        {
            "trace_id": state["trace_id"],
            "request": state["request"].model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in state["evidence"]],
            "scores": [item.model_dump(mode="json") for item in state["scores"]],
            "plan": state["plan"].model_dump(mode="json"),
            "fda_provenance": state["fda_provenance"],
            "warnings": state.get("warnings", []),
        },
    )
    return {
        "artifacts": [artifact],
        "stage_events": _event(
            state,
            "audit_reporting",
            started,
            len(state["scores"]),
            1,
            "Wrote source evidence, score components, plan, provenance, and trace identifier.",
        ),
    }


def verification(state: WorkflowState) -> dict:
    started = _now()
    failures = []
    if len(state["plan"].items) != len(state["assets"]):
        failures.append("plan does not cover every asset")
    if any(item.unit_attribution for item in state["evidence"]):
        failures.append("public evidence was attributed to a hospital unit")
    if any(not item.source_urls for item in state["evidence"]):
        failures.append("one or more assets lack a public evidence URL")
    if any(not artifact.path.exists() for artifact in state["artifacts"]):
        failures.append("one or more audit artifacts are missing")
    if failures:
        raise RuntimeError("Verification failed: " + "; ".join(failures))
    return {
        "verification_ok": True,
        "stage_events": _event(
            state,
            "verification",
            started,
            len(state["artifacts"]),
            len(state["artifacts"]),
            "Verified fleet coverage, citations, non-attribution, and audit artifact integrity.",
        ),
    }


def build_workflow_graph():
    graph = StateGraph(WorkflowState)
    nodes = {
        "maude_ingestion": maude_ingestion,
        "correlation": correlation,
        "risk_scoring": risk_scoring,
        "regulatory_grounding": regulatory_grounding,
        "retirement_planning": retirement_planning,
        "audit_reporting": audit_reporting,
        "verification": verification,
    }
    for name, node in nodes.items():
        graph.add_node(name, node)
    graph.add_edge(START, STAGES[0])
    for current, following in zip(STAGES, STAGES[1:]):
        graph.add_edge(current, following)
    graph.add_edge(STAGES[-1], END)
    return graph.compile()


def run_workflow(request: RetirementRequest, services: WorkflowServices | None = None) -> WorkflowResult:
    services = services or WorkflowServices.cached(
        output_dir=request.output_dir,
        live_fda=request.live_fda,
        sandbox_provider=request.sandbox_provider,
    )
    initial: WorkflowState = {
        "request": request,
        "services": services,
        "trace_id": uuid4().hex,
        "stage_events": [],
        "warnings": [],
        "artifacts": [],
        "fda_provenance": {},
    }
    state = build_workflow_graph().invoke(initial)
    return WorkflowResult(
        status="completed",
        trace_id=state["trace_id"],
        request=request,
        stage_events=state["stage_events"],
        evidence=state["evidence"],
        scores=state["scores"],
        plan=state["plan"],
        artifacts=state["artifacts"],
        warnings=state.get("warnings", []),
        sandbox_provider=state["sandbox_provider"],
        fda_provenance=state["fda_provenance"],
    )
