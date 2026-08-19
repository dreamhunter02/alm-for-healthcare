from datetime import date

from healthcare_alm.analysis.correlate import correlate_assets
from healthcare_alm.models import InventoryAsset, MAUDEEvent, RecallRecord


def _asset(model="FS-900"):
    return InventoryAsset(
        asset_id="PUMP-001",
        manufacturer="Acme Medical",
        brand_name="FlowSafe",
        model_number=model,
        serial_alias="SN-001",
        department="ICU",
        manufacture_date=date(2015, 1, 1),
        install_date=date(2016, 1, 1),
        expected_service_years=10,
        acquisition_cost=24000,
        utilization_hours=31000,
        pm_compliance_pct=88,
        corrective_maintenance_count=5,
        days_out_of_service=14,
        last_inspection_date=date(2026, 1, 1),
        local_malfunction_count=4,
        product_code="FRN",
    )


def _event(manufacturer="ACME MEDICAL", model="FS 900"):
    return MAUDEEvent(
        report_number="MDR-1001",
        event_date=date(2026, 1, 10),
        event_type="Injury",
        manufacturer=manufacturer,
        brand_name="FLOWSAFE",
        model_number=model,
        product_code="FRN",
        source_url="https://api.fda.gov/device/event.json?search=FRN",
    )


def test_correlation_prefers_model_and_never_claims_unit_causation():
    evidence = correlate_assets([_asset()], [], [_event()], [], date(2026, 8, 15))[0]
    assert evidence.match_tier == "manufacturer_model"
    assert evidence.unit_attribution is False
    assert "public signal" in evidence.disclaimer.lower()


def test_unmatched_asset_uses_product_code_fallback():
    evidence = correlate_assets([_asset()], [], [_event("OTHER MAKER", "OTHER")], [], date(2026, 8, 15))[0]
    assert evidence.match_tier == "product_code_only"
    assert evidence.confidence == "low"


def test_generic_infusion_pump_words_do_not_create_false_recall_match():
    asset = _asset(model="NA").model_copy(
        update={
            "manufacturer": "Baxter Healthcare Corporation",
            "brand_name": "Spectrum Infusion Pump",
        }
    )
    recall = RecallRecord(
        recall_number="R-OTHER",
        manufacturer="BAXTER HEALTHCARE CORP",
        product_description="Baxter Colleague Infusion Pump",
        model_number="OTHER 100",
        product_code="FRN",
        recall_status="Open",
        reason_for_recall="Example",
        source_url="https://api.fda.gov/device/recall.json?search=FRN",
    )

    evidence = correlate_assets([asset], [], [_event()], [recall], date(2026, 8, 15))[0]

    assert evidence.recall_records == []
