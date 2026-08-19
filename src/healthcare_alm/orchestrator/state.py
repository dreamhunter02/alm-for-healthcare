from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, TypedDict

from healthcare_alm.fda.client import FDAClient
from healthcare_alm.mcp.recall_server import RecallService
from healthcare_alm.models import (
    ArtifactRef,
    AssetEvidence,
    FDAResponse,
    InventoryAsset,
    MaintenanceEvent,
    MAUDEEvent,
    RecallRecord,
    RetirementPlan,
    RetirementRequest,
    RiskScore,
    StageEvent,
)
from healthcare_alm.sandbox.openshell import create_sandbox_runner


@dataclass
class WorkflowServices:
    fda_client: FDAClient
    recall_service: RecallService
    sandbox_runner: Any
    inventory_path: Path
    maintenance_path: Path
    output_dir: Path
    as_of_date: date

    @classmethod
    def cached(
        cls,
        output_dir: Path | str = Path("output"),
        as_of_date: date = date(2026, 8, 15),
        live_fda: bool = False,
        sandbox_provider: str = "auto",
    ) -> WorkflowServices:
        client = FDAClient(fixture_dir=Path("data/fixtures"))
        return cls(
            fda_client=client,
            recall_service=RecallService(client, live=live_fda),
            sandbox_runner=create_sandbox_runner(sandbox_provider),
            inventory_path=Path("data/mock_inventory.csv"),
            maintenance_path=Path("data/mock_maintenance.csv"),
            output_dir=Path(output_dir),
            as_of_date=as_of_date,
        )


class WorkflowState(TypedDict, total=False):
    request: RetirementRequest
    services: WorkflowServices
    trace_id: str
    stage_events: list[StageEvent]
    warnings: list[str]
    maude_response: FDAResponse
    assets: list[InventoryAsset]
    maintenance: list[MaintenanceEvent]
    maude: list[MAUDEEvent]
    recalls: list[RecallRecord]
    evidence: list[AssetEvidence]
    scores: list[RiskScore]
    plan: RetirementPlan
    artifacts: list[ArtifactRef]
    sandbox_provider: str
    fda_provenance: dict[str, str]
    verification_ok: bool
