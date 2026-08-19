from __future__ import annotations

import re
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from healthcare_alm.analysis.correlate import correlate_assets
from healthcare_alm.analysis.planner import build_retirement_plan
from healthcare_alm.analysis.scoring import score_asset
from healthcare_alm.data.setup_database import build_database, load_inventory, load_maintenance
from healthcare_alm.fda.client import FDAClient
from healthcare_alm.fda.normalize import normalize_maude, normalize_recalls, normalize_text
from healthcare_alm.models import ScoreConfig
from healthcare_alm.retrievers.sql import ReadOnlySQLRetriever

DEFAULT_AS_OF_DATE = date(2026, 8, 15)
SAFETY_NOTICE = (
    "Public MAUDE reports are model/product-level safety signals. They cannot be linked to a specific hospital "
    "asset and do not provide an exposure denominator for an incidence or failure rate."
)


class MedicalDeviceTools:
    """Deterministic domain operations exposed to the language model as tools."""

    def __init__(
        self,
        db_path: Path | str = Path("output/agent-data/healthcare_alm.db"),
        fixture_dir: Path | str = Path("data/fixtures"),
        inventory_path: Path | str = Path("data/mock_inventory.csv"),
        maintenance_path: Path | str = Path("data/mock_maintenance.csv"),
        as_of_date: date = DEFAULT_AS_OF_DATE,
        live_fda: bool = False,
    ) -> None:
        self.db_path = Path(db_path)
        self.fixture_dir = Path(fixture_dir)
        self.inventory_path = Path(inventory_path)
        self.maintenance_path = Path(maintenance_path)
        self.as_of_date = as_of_date
        self.live_fda = live_fda
        self.client = FDAClient(fixture_dir=self.fixture_dir)
        self._prepare_database()

    def _load_domain_data(self):
        assets = load_inventory(self.inventory_path)
        maintenance = load_maintenance(self.maintenance_path)
        maude_response = self.client.fetch_maude("FRN", live=self.live_fda)
        recall_response = self.client.fetch_recalls("FRN", live=self.live_fda)
        maude = normalize_maude(maude_response.results, maude_response.source_url)
        recalls = normalize_recalls(recall_response.results, recall_response.source_url)
        return assets, maintenance, maude, recalls

    def _prepare_database(self) -> None:
        assets, maintenance, maude, recalls = self._load_domain_data()
        build_database(self.db_path, assets, maintenance, maude, recalls)

    def describe_hospital_database(self) -> dict[str, Any]:
        tables: dict[str, list[dict[str, Any]]] = {}
        uri = f"file:{self.db_path.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            names = connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            for row in names:
                safe_name = str(row["name"]).replace('"', '""')
                columns = connection.execute(f'PRAGMA table_info("{safe_name}")').fetchall()
                tables[row["name"]] = [
                    {"name": column["name"], "type": column["type"], "nullable": not bool(column["notnull"])}
                    for column in columns
                ]
        return {
            "database": str(self.db_path),
            "tables": tables,
            "data_classification": "fictional workshop data",
            "semantics": {
                "inventory": "One row per fictional hospital infusion pump.",
                "maintenance_events": (
                    "Fictional illustrative work-order samples; downtime_days is event-level and these rows are not a "
                    "complete cumulative downtime history."
                ),
                "inventory.days_out_of_service": (
                    "Authoritative cumulative per-asset downtime total for fleet, department, and Pareto analyses."
                ),
                "maude_events": "Public FDA safety reports normalized at product/model level.",
                "recalls": "Public FDA recall records; matches never establish unit causality.",
            },
            "safety_notice": SAFETY_NOTICE,
        }

    def query_hospital_database(self, sql: str) -> dict[str, Any]:
        if re.search(r"\b(?:recalls|maude_events)\b", sql, flags=re.IGNORECASE):
            return {
                "status": "query_error",
                "error": "FDA tables are not available through the hospital SQL tool.",
                "retry_guidance": "Use the dedicated FDA tools: search_maude_events or search_device_recalls.",
            }
        try:
            rows = ReadOnlySQLRetriever(self.db_path).query(sql)
        except sqlite3.DatabaseError as exc:
            return {
                "status": "query_error",
                "error": str(exc),
                "retry_guidance": "Inspect describe_hospital_database and retry with valid columns.",
            }
        return {
            "status": "success",
            "row_count": len(rows),
            "rows": rows,
            "data_classification": "fictional workshop data",
        }

    def search_maude_events(
        self,
        product_code: str = "FRN",
        manufacturer: str | None = None,
        model_number: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        response = self.client.fetch_maude(product_code, live=self.live_fda)
        records = normalize_maude(response.results, response.source_url)
        if manufacturer:
            manufacturer_text = normalize_text(manufacturer)
            records = [record for record in records if manufacturer_text in normalize_text(record.manufacturer)]
        if model_number:
            model_text = normalize_text(model_number)
            records = [record for record in records if model_text in normalize_text(record.model_number)]
        return {
            "status": "available_matches" if records else "available_no_matches",
            "records": [record.model_dump(mode="json") for record in records[:limit]],
            "source_url": response.source_url,
            "provenance": response.provenance,
            "safety_notice": SAFETY_NOTICE,
        }

    def search_device_recalls(
        self,
        product_code: str = "FRN",
        manufacturer: str | None = None,
        model_number: str | None = None,
    ) -> dict[str, Any]:
        response = self.client.fetch_recalls(product_code, live=self.live_fda)
        records = normalize_recalls(response.results, response.source_url)
        if manufacturer:
            manufacturer_text = normalize_text(manufacturer)
            records = [
                record for record in records if manufacturer_text.split()[0] in normalize_text(record.manufacturer)
            ]
        if model_number:
            model_text = normalize_text(model_number)
            records = [
                record
                for record in records
                if model_text in normalize_text(f"{record.model_number} {record.product_description}")
            ]
        return {
            "status": "available_matches" if records else "available_no_matches",
            "records": [record.model_dump(mode="json") for record in records],
            "source_url": response.source_url,
            "provenance": response.provenance,
            "safety_notice": SAFETY_NOTICE,
        }

    def _scores(self, asset_ids: list[str] | None = None, department: str | None = None):
        assets, maintenance, maude, recalls = self._load_domain_data()
        evidence = correlate_assets(assets, maintenance, maude, recalls, self.as_of_date)
        if asset_ids:
            selected = set(asset_ids)
            evidence = [item for item in evidence if item.asset.asset_id in selected]
        if department:
            department_text = normalize_text(department)
            evidence = [item for item in evidence if normalize_text(item.asset.department) == department_text]
        return [score_asset(item, ScoreConfig()) for item in evidence]

    def score_retirement_risk(
        self,
        asset_ids: list[str] | None = None,
        department: str | None = None,
    ) -> dict[str, Any]:
        scores = sorted(self._scores(asset_ids, department), key=lambda score: (-score.total, score.asset_id))
        return {
            "formula_version": ScoreConfig().formula_version,
            "scores": [score.model_dump(mode="json") for score in scores],
            "safety_notice": "Recommendations require human clinical-engineering review.",
        }

    def build_replacement_plan(
        self,
        annual_budget: Decimal = Decimal("120000"),
        asset_ids: list[str] | None = None,
        department: str | None = None,
    ) -> dict[str, Any]:
        budget = Decimal(str(annual_budget))
        plan = build_retirement_plan(self._scores(asset_ids, department), budget)
        result = plan.model_dump(mode="json")
        result["remaining_budget"] = str(budget - plan.current_phase_spend)
        result["safety_notice"] = "Recommendations require human clinical-engineering review."
        return result
