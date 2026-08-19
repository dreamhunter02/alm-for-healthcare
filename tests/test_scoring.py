from datetime import date

from healthcare_alm.analysis.scoring import score_asset
from healthcare_alm.models import AssetEvidence, InventoryAsset, RecallRecord, ScoreConfig


def _high_risk_evidence():
    asset = InventoryAsset(
        asset_id="PUMP-HIGH",
        manufacturer="Zyno Medical LLC",
        brand_name="Z-800 Infusion System",
        model_number="Z-800F",
        serial_alias="SN-HIGH",
        department="ICU",
        manufacture_date=date(2012, 1, 1),
        install_date=date(2013, 1, 1),
        expected_service_years=10,
        acquisition_cost=30000,
        utilization_hours=50000,
        pm_compliance_pct=75,
        corrective_maintenance_count=9,
        days_out_of_service=40,
        last_inspection_date=date(2025, 10, 1),
        local_malfunction_count=8,
        product_code="FRN",
    )
    recall = RecallRecord(
        recall_number="95382",
        event_date=date(2024, 9, 13),
        manufacturer="ZYNO MEDICAL LLC",
        product_description="Z-800 Infusion System",
        model_number="Z 800F",
        product_code="FRN",
        recall_status="Open, Classified",
        reason_for_recall="Air in line software defect",
        source_url="https://api.fda.gov/device/recall.json?search=FRN",
    )
    return AssetEvidence(
        asset=asset,
        as_of_date=date(2026, 8, 15),
        match_tier="manufacturer_model",
        confidence="high",
        maintenance_events_24m=6,
        recent_maude_count=12,
        older_maude_count=3,
        event_type_counts={"Injury": 4, "Malfunction": 8},
        recall_records=[recall],
        source_urls=[recall.source_url],
    )


def test_score_components_sum_and_retire_threshold():
    score = score_asset(_high_risk_evidence(), ScoreConfig())
    assert score.total == sum(component.points for component in score.components)
    assert 0 <= score.total <= 100
    assert score.action == "retire"
    assert score.formula_version == "healthcare-alm-risk-v1"


def test_low_evidence_reduces_confidence_without_implying_safety():
    evidence = _high_risk_evidence().model_copy(
        update={
            "match_tier": "product_code_only",
            "confidence": "low",
            "recent_maude_count": 0,
            "older_maude_count": 0,
            "event_type_counts": {},
            "recall_records": [],
        }
    )
    score = score_asset(evidence, ScoreConfig())
    assert score.confidence == "low"
    assert "missing" in score.evidence_note.lower()
    assert score.total > 0


def test_product_code_only_public_signals_are_confidence_capped():
    evidence = _high_risk_evidence().model_copy(update={"confidence": "low", "match_tier": "product_code_only"})

    score = score_asset(evidence, ScoreConfig())

    public_points = {component.name: component.points for component in score.components}
    assert public_points["maude_trend"] <= 5
    assert public_points["event_severity_mix"] <= 3
