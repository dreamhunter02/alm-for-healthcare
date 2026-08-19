from __future__ import annotations

from collections import Counter
from datetime import date

from healthcare_alm.fda.normalize import normalize_text
from healthcare_alm.models import AssetEvidence, InventoryAsset, MaintenanceEvent, MAUDEEvent, RecallRecord

GENERIC_DEVICE_TOKENS = {"DEVICE", "INFUSION", "MEDICAL", "PUMP", "SYSTEM", "UNIT"}


def _brand_tokens(value: str) -> set[str]:
    return {
        token
        for token in normalize_text(value).split()
        if len(token) >= 4 and token not in GENERIC_DEVICE_TOKENS
    }


def _manufacturer_matches(asset_name: str, evidence_name: str) -> bool:
    asset = normalize_text(asset_name)
    evidence = normalize_text(evidence_name)
    return asset == evidence or bool(asset and evidence and asset.split()[0] == evidence.split()[0])


def _brand_matches(asset: InventoryAsset, event: MAUDEEvent) -> bool:
    asset_tokens = _brand_tokens(asset.brand_name)
    event_tokens = _brand_tokens(event.brand_name)
    return bool(asset_tokens & event_tokens)


def _match_events(asset: InventoryAsset, events: list[MAUDEEvent]) -> tuple[list[MAUDEEvent], str, str]:
    same_code = [event for event in events if event.product_code == asset.product_code]
    model = normalize_text(asset.model_number)
    if model not in {"", "NA", "UNKNOWN"}:
        exact = [
            event
            for event in same_code
            if _manufacturer_matches(asset.manufacturer, event.manufacturer) and event.model_number == model
        ]
        if exact:
            return exact, "manufacturer_model", "high"
    brand = [
        event
        for event in same_code
        if _manufacturer_matches(asset.manufacturer, event.manufacturer) and _brand_matches(asset, event)
    ]
    if brand:
        return brand, "manufacturer_brand", "medium"
    if same_code:
        return same_code, "product_code_only", "low"
    return [], "none", "low"


def _match_recalls(asset: InventoryAsset, recalls: list[RecallRecord]) -> list[RecallRecord]:
    model = normalize_text(asset.model_number)
    brand_tokens = _brand_tokens(asset.brand_name)
    matches = []
    for recall in recalls:
        if recall.product_code != asset.product_code or not _manufacturer_matches(
            asset.manufacturer, recall.manufacturer
        ):
            continue
        description = normalize_text(f"{recall.product_description} {recall.model_number}")
        if (model not in {"", "NA", "UNKNOWN"} and model in description) or any(
            token in description for token in brand_tokens
        ):
            matches.append(recall)
    return matches


def correlate_assets(
    assets: list[InventoryAsset],
    maintenance: list[MaintenanceEvent],
    maude: list[MAUDEEvent],
    recalls: list[RecallRecord],
    as_of: date,
) -> list[AssetEvidence]:
    evidence_rows = []
    recent_cutoff = date(as_of.year - 2, as_of.month, min(as_of.day, 28))
    older_cutoff = date(as_of.year - 4, as_of.month, min(as_of.day, 28))
    for asset in assets:
        matched_events, match_tier, confidence = _match_events(asset, maude)
        maintenance_count = sum(
            1
            for event in maintenance
            if event.asset_id == asset.asset_id
            and event.event_type.lower() == "corrective"
            and event.event_date >= recent_cutoff
        )
        recent = [event for event in matched_events if event.event_date and event.event_date >= recent_cutoff]
        older = [
            event for event in matched_events if event.event_date and older_cutoff <= event.event_date < recent_cutoff
        ]
        matched_recalls = _match_recalls(asset, recalls)
        urls = sorted(
            {event.source_url for event in matched_events} | {recall.source_url for recall in matched_recalls}
        )
        evidence_rows.append(
            AssetEvidence(
                asset=asset,
                as_of_date=as_of,
                match_tier=match_tier,
                confidence=confidence,
                maintenance_events_24m=maintenance_count,
                recent_maude_count=len(recent),
                older_maude_count=len(older),
                event_type_counts=dict(Counter(event.event_type for event in matched_events)),
                recall_records=matched_recalls,
                source_urls=urls,
            )
        )
    return evidence_rows
