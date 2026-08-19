from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from healthcare_alm.models import MAUDEEvent, RecallRecord


def normalize_text(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def parse_fda_date(value: Any) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def normalize_maude(records: list[dict[str, Any]], source_url: str) -> list[MAUDEEvent]:
    normalized: dict[str, MAUDEEvent] = {}
    for record in records:
        device = next(iter(record.get("device") or [{}]), {})
        report_number = str(record.get("report_number") or record.get("mdr_report_key") or "").strip()
        if not report_number:
            continue
        openfda = device.get("openfda") or {}
        product_code = device.get("device_report_product_code") or next(iter(openfda.get("product_code") or []), "")
        normalized[report_number] = MAUDEEvent(
            report_number=report_number,
            event_date=parse_fda_date(record.get("date_received") or record.get("date_of_event")),
            event_type=str(record.get("event_type") or "Unknown"),
            manufacturer=normalize_text(device.get("manufacturer_d_name")),
            brand_name=normalize_text(device.get("brand_name")),
            model_number=normalize_text(device.get("model_number")),
            product_code=normalize_text(product_code),
            source_url=source_url,
        )
    return sorted(normalized.values(), key=lambda event: event.report_number)


def normalize_recalls(records: list[dict[str, Any]], source_url: str) -> list[RecallRecord]:
    normalized: dict[str, RecallRecord] = {}
    for record in records:
        recall_number = str(record.get("res_event_number") or record.get("recall_number") or "").strip()
        if not recall_number:
            continue
        normalized[recall_number] = RecallRecord(
            recall_number=recall_number,
            event_date=parse_fda_date(record.get("event_date_initiated") or record.get("event_date_posted")),
            manufacturer=normalize_text(record.get("recalling_firm") or record.get("manufacturer_name")),
            product_description=str(record.get("product_description") or ""),
            model_number=normalize_text(record.get("code_info") or record.get("model_number")),
            product_code=normalize_text(record.get("product_code")),
            recall_status=str(record.get("recall_status") or record.get("status") or "Unknown"),
            reason_for_recall=str(record.get("reason_for_recall") or ""),
            source_url=source_url,
        )
    return sorted(normalized.values(), key=lambda recall: recall.recall_number)
