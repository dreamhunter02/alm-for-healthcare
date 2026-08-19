from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

OPENFDA_DISCLAIMER = (
    "Do not rely on openFDA to make decisions regarding medical care. "
    "MAUDE reports are public signals and cannot be attributed to a specific hospital asset."
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class FDAResponse(FrozenModel):
    endpoint: str
    product_code: str
    source_url: str
    provenance: Literal["live", "cached", "cached_fallback"]
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_updated: str | None = None
    results: list[dict[str, Any]]
    disclaimer: str = OPENFDA_DISCLAIMER


class MAUDEEvent(FrozenModel):
    report_number: str
    event_date: date | None = None
    event_type: str
    manufacturer: str
    brand_name: str
    model_number: str
    product_code: str
    source_url: str


class RecallRecord(FrozenModel):
    recall_number: str
    event_date: date | None = None
    manufacturer: str
    product_description: str
    model_number: str
    product_code: str
    recall_status: str
    reason_for_recall: str
    source_url: str


class InventoryAsset(FrozenModel):
    asset_id: str
    manufacturer: str
    brand_name: str
    model_number: str
    serial_alias: str
    department: str
    manufacture_date: date
    install_date: date
    expected_service_years: int
    acquisition_cost: Decimal
    utilization_hours: int
    pm_compliance_pct: float
    corrective_maintenance_count: int
    days_out_of_service: int
    last_inspection_date: date
    local_malfunction_count: int
    product_code: str = "FRN"


class MaintenanceEvent(FrozenModel):
    event_id: str
    asset_id: str
    event_date: date
    event_type: str
    description: str
    downtime_days: int = 0


class DatabaseSummary(FrozenModel):
    db_path: Path
    inventory_count: int
    maintenance_count: int
    maude_count: int
    recall_count: int


class ArtifactRef(FrozenModel):
    artifact_id: str
    path: Path
    media_type: str
    sha256: str
    size_bytes: int


class RetirementRequest(FrozenModel):
    product_code: str = "FRN"
    budget: Decimal = Decimal("120000")
    live_fda: bool = False
    sandbox_provider: Literal["auto", "local", "openshell"] = "auto"
    output_dir: Path = Path("output")


EvidenceConfidence = Literal["high", "medium", "low"]
MatchTier = Literal["manufacturer_model", "manufacturer_brand", "product_code_only", "none"]


class AssetEvidence(FrozenModel):
    asset: InventoryAsset
    as_of_date: date
    match_tier: MatchTier
    confidence: EvidenceConfidence
    maintenance_events_24m: int = 0
    recent_maude_count: int = 0
    older_maude_count: int = 0
    event_type_counts: dict[str, int] = Field(default_factory=dict)
    recall_records: list[RecallRecord] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    unit_attribution: bool = False
    disclaimer: str = OPENFDA_DISCLAIMER


class ScoreConfig(FrozenModel):
    formula_version: str = "healthcare-alm-risk-v1"
    retire_threshold: int = 70
    replace_threshold: int = 50
    age_max: int = 30
    trend_max: int = 25
    severity_max: int = 20
    recall_max: int = 15
    maintenance_max: int = 10


class ScoreComponent(FrozenModel):
    name: str
    points: int
    max_points: int
    inputs: dict[str, Any]
    explanation: str


class RiskScore(FrozenModel):
    asset_id: str
    total: int
    action: Literal["retire", "plan_replacement", "maintain"]
    confidence: EvidenceConfidence
    match_tier: MatchTier
    components: list[ScoreComponent]
    estimated_cost: Decimal
    formula_version: str = "healthcare-alm-risk-v1"
    evidence_note: str = "Public FDA evidence is model/product-level and is not unit attribution."


class RetirementPlanItem(FrozenModel):
    asset_id: str
    action: Literal["retire", "plan_replacement", "maintain"]
    risk_score: int
    estimated_cost: Decimal
    phase: Literal["current_budget", "next_horizon", "monitor"]
    evidence_confidence: EvidenceConfidence
    rationale: str


class RetirementPlan(FrozenModel):
    annual_budget: Decimal
    current_phase_spend: Decimal
    items: list[RetirementPlanItem]
    current_phase: list[RetirementPlanItem]
    next_phase: list[RetirementPlanItem]


class SandboxResult(FrozenModel):
    status: Literal["completed", "failed", "timeout"]
    provider: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    environment_keys: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)


class RecallSearchResult(FrozenModel):
    status: Literal["available_matches", "available_no_matches", "unavailable"]
    records: list[RecallRecord] = Field(default_factory=list)
    source_url: str = ""
    provenance: Literal["live", "cached", "cached_fallback", "unavailable"]
    message: str = ""
    disclaimer: str = OPENFDA_DISCLAIMER


class StageEvent(FrozenModel):
    stage: str
    status: Literal["completed", "failed"]
    started_at: datetime
    completed_at: datetime
    input_count: int = 0
    output_count: int = 0
    retry_count: int = 0
    trace_id: str
    message: str = ""


class WorkflowResult(FrozenModel):
    status: Literal["completed", "failed"]
    trace_id: str
    request: RetirementRequest
    stage_events: list[StageEvent]
    evidence: list[AssetEvidence]
    scores: list[RiskScore]
    plan: RetirementPlan
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sandbox_provider: str
    fda_provenance: dict[str, str] = Field(default_factory=dict)
