import sqlite3
from datetime import date

from healthcare_alm.data.setup_database import build_database, load_inventory, load_maintenance
from healthcare_alm.models import InventoryAsset, MaintenanceEvent, MAUDEEvent, RecallRecord


def test_build_database_creates_healthcare_tables(tmp_path):
    assets = [
        InventoryAsset(
            asset_id="PUMP-001",
            manufacturer="Acme Medical",
            brand_name="FlowSafe",
            model_number="FS-900",
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
    ]
    maintenance = [
        MaintenanceEvent(
            event_id="M-001",
            asset_id="PUMP-001",
            event_date=date(2026, 2, 1),
            event_type="corrective",
            description="Occlusion alarm recurring",
            downtime_days=2,
        )
    ]
    maude = [
        MAUDEEvent(
            report_number="MDR-1001",
            event_date=date(2026, 1, 10),
            event_type="Malfunction",
            manufacturer="ACME MEDICAL",
            brand_name="FLOWSAFE",
            model_number="FS 900",
            product_code="FRN",
            source_url="https://api.fda.gov/device/event.json?search=FRN",
        )
    ]
    recalls = [
        RecallRecord(
            recall_number="Z-1000-2026",
            event_date=date(2026, 1, 5),
            manufacturer="ACME MEDICAL",
            product_description="FlowSafe FS-900 infusion pump",
            model_number="FS 900",
            product_code="FRN",
            recall_status="Ongoing",
            reason_for_recall="Unexpected shutdown",
            source_url="https://api.fda.gov/device/recall.json?search=FRN",
        )
    ]

    summary = build_database(tmp_path / "healthcare.db", assets, maintenance, maude, recalls)
    assert summary.inventory_count == 1
    with sqlite3.connect(summary.db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[1] for row in conn.execute("PRAGMA index_list('maude_events')")}
    assert {"inventory", "maintenance_events", "maude_events", "recalls", "run_metadata"} <= tables
    assert "idx_maude_product_code" in indexes


def test_checked_in_mock_data_loads_twelve_assets():
    assets = load_inventory("data/mock_inventory.csv")
    maintenance = load_maintenance("data/mock_maintenance.csv")
    assert len(assets) == 12
    assert {asset.department for asset in assets} >= {"ICU", "Emergency", "Operating Room"}
    assert all(event.asset_id.startswith("PUMP-") for event in maintenance)
