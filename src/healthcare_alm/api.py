from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from healthcare_alm.models import RetirementRequest, WorkflowResult
from healthcare_alm.orchestrator.graph import run_workflow
from healthcare_alm.reporting.audit import build_audit_bundle


class DemoRunRequest(BaseModel):
    budget: Decimal = Decimal("120000")
    live_fda: bool = False
    sandbox_provider: str = "auto"


class DemoService:
    def __init__(self, output_dir: Path | str = Path("output/latest")) -> None:
        self.output_dir = Path(output_dir)
        self.latest: WorkflowResult | None = None

    def run(self, request: DemoRunRequest) -> WorkflowResult:
        workflow_request = RetirementRequest(
            budget=request.budget,
            live_fda=request.live_fda,
            sandbox_provider=request.sandbox_provider,
            output_dir=self.output_dir,
        )
        self.latest = run_workflow(workflow_request)
        build_audit_bundle(self.latest, self.output_dir / "bundle")
        return self.latest

    def require_latest(self) -> WorkflowResult:
        if self.latest is None:
            raise HTTPException(status_code=404, detail="Run the demo first.")
        return self.latest


def create_app(service: DemoService | None = None) -> FastAPI:
    service = service or DemoService()
    app = FastAPI(title="Healthcare ALM Workshop", version="0.1.0")
    app.state.demo_service = service

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/demo/run")
    def run_demo(request: DemoRunRequest) -> dict:
        return service.run(request).model_dump(mode="json")

    @app.get("/api/assets")
    def assets() -> list[dict]:
        result = service.require_latest()
        score_by_id = {score.asset_id: score for score in result.scores}
        return [
            {
                "asset": evidence.asset.model_dump(mode="json"),
                "evidence": evidence.model_dump(mode="json", exclude={"asset"}),
                "score": score_by_id[evidence.asset.asset_id].model_dump(mode="json"),
            }
            for evidence in result.evidence
        ]

    @app.get("/api/plan")
    def plan() -> dict:
        return service.require_latest().plan.model_dump(mode="json")

    @app.get("/api/audit")
    def audit() -> dict:
        result = service.require_latest()
        return {
            "trace_id": result.trace_id,
            "stages": [event.model_dump(mode="json") for event in result.stage_events],
            "fda_provenance": result.fda_provenance,
            "sandbox_provider": result.sandbox_provider,
            "warnings": result.warnings,
            "artifacts": [artifact.model_dump(mode="json") for artifact in result.artifacts],
        }

    @app.get("/")
    def dashboard() -> FileResponse:
        return FileResponse(Path(__file__).with_name("static") / "index.html")

    return app


app = create_app()
