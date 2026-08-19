# SPDX-FileCopyrightText: Copyright (c) 2023-2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0
"""SQLite builder adapted from the original ALM NASA dataset processor."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from healthcare_alm.models import DatabaseSummary, InventoryAsset, MaintenanceEvent, MAUDEEvent, RecallRecord


def _frame(items: list[BaseModel], model: type[BaseModel]) -> pd.DataFrame:
    if items:
        return pd.DataFrame([item.model_dump(mode="json") for item in items])
    return pd.DataFrame(columns=list(model.model_fields))


def load_inventory(path: Path | str) -> list[InventoryAsset]:
    records = pd.read_csv(path, dtype={"serial_alias": str, "product_code": str}, keep_default_na=False).to_dict(
        orient="records"
    )
    return [InventoryAsset.model_validate(record) for record in records]


def load_maintenance(path: Path | str) -> list[MaintenanceEvent]:
    records = pd.read_csv(path).to_dict(orient="records")
    return [MaintenanceEvent.model_validate(record) for record in records]


def build_database(
    db_path: Path | str,
    assets: list[InventoryAsset],
    maintenance: list[MaintenanceEvent],
    maude: list[MAUDEEvent],
    recalls: list[RecallRecord],
) -> DatabaseSummary:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        _frame(assets, InventoryAsset).to_sql("inventory", conn, if_exists="replace", index=False)
        _frame(maintenance, MaintenanceEvent).to_sql("maintenance_events", conn, if_exists="replace", index=False)
        _frame(maude, MAUDEEvent).to_sql("maude_events", conn, if_exists="replace", index=False)
        _frame(recalls, RecallRecord).to_sql("recalls", conn, if_exists="replace", index=False)
        pd.DataFrame([{"created_at": datetime.now(UTC).isoformat(), "schema_version": "healthcare-alm-v1"}]).to_sql(
            "run_metadata", conn, if_exists="replace", index=False
        )
        indexes = [
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_asset ON inventory(asset_id)",
            "CREATE INDEX IF NOT EXISTS idx_maintenance_asset ON maintenance_events(asset_id)",
            "CREATE INDEX IF NOT EXISTS idx_maude_product_code ON maude_events(product_code)",
            "CREATE INDEX IF NOT EXISTS idx_maude_model ON maude_events(manufacturer, model_number)",
            "CREATE INDEX IF NOT EXISTS idx_recall_product_code ON recalls(product_code)",
        ]
        for statement in indexes:
            conn.execute(statement)
        conn.execute(
            "CREATE VIEW IF NOT EXISTS fleet_age_summary AS "
            "SELECT department, COUNT(*) AS asset_count, AVG(expected_service_years) AS avg_service_years "
            "FROM inventory GROUP BY department"
        )
        conn.commit()
    return DatabaseSummary(
        db_path=path,
        inventory_count=len(assets),
        maintenance_count=len(maintenance),
        maude_count=len(maude),
        recall_count=len(recalls),
    )
