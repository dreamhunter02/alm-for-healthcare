from __future__ import annotations

from healthcare_alm.models import AssetEvidence, RiskScore, ScoreComponent, ScoreConfig


def _clamp(value: float, maximum: int) -> int:
    return max(0, min(maximum, round(value)))


def score_asset(evidence: AssetEvidence, config: ScoreConfig) -> RiskScore:
    asset = evidence.asset
    age_years = (evidence.as_of_date - asset.install_date).days / 365.25
    age_ratio = age_years / asset.expected_service_years
    if age_ratio <= 0.5:
        age_points = 0
    elif age_ratio <= 1.0:
        age_points = _clamp((age_ratio - 0.5) * 40, config.age_max)
    else:
        age_points = _clamp(20 + (age_ratio - 1.0) * 40, config.age_max)

    recent, older = evidence.recent_maude_count, evidence.older_maude_count
    if recent == 0:
        trend_points = 0
    elif older == 0:
        trend_points = _clamp(10 + recent * 2, config.trend_max)
    else:
        trend_points = _clamp(max(0.0, (recent / older - 1.0) * 12.5), config.trend_max)

    event_total = sum(evidence.event_type_counts.values())
    death_count = evidence.event_type_counts.get("Death", 0)
    injury_count = evidence.event_type_counts.get("Injury", 0)
    if death_count:
        severity_points = config.severity_max
    elif event_total:
        severity_points = _clamp((injury_count / event_total) * 30 + min(event_total / 10 * 5, 5), config.severity_max)
    else:
        severity_points = 0

    # Broad product-code signals provide context, not model-level evidence.
    # Keep them visible without allowing fleet-wide counts to dominate a unit decision.
    if evidence.match_tier == "product_code_only":
        trend_points = min(trend_points, 5)
        severity_points = min(severity_points, 3)

    statuses = " ".join(recall.recall_status.lower() for recall in evidence.recall_records)
    if "open" in statuses or "ongoing" in statuses:
        recall_points = config.recall_max
    elif evidence.recall_records and ("correct" in statuses or "classified" in statuses):
        recall_points = min(10, config.recall_max)
    elif evidence.recall_records:
        recall_points = min(5, config.recall_max)
    else:
        recall_points = 0

    maintenance_points = _clamp(
        evidence.maintenance_events_24m * 2 + min(asset.local_malfunction_count, 5), config.maintenance_max
    )
    components = [
        ScoreComponent(
            name="age_service_life",
            points=age_points,
            max_points=config.age_max,
            inputs={"age_years": round(age_years, 2), "expected_service_years": asset.expected_service_years},
            explanation="Installed age relative to configured expected service life.",
        ),
        ScoreComponent(
            name="maude_trend",
            points=trend_points,
            max_points=config.trend_max,
            inputs={"recent_count": recent, "older_count": older, "match_tier": evidence.match_tier},
            explanation=(
                "Change in matched public MAUDE report counts; not an incidence rate. "
                "Product-code-only evidence is confidence-capped."
            ),
        ),
        ScoreComponent(
            name="event_severity_mix",
            points=severity_points,
            max_points=config.severity_max,
            inputs=evidence.event_type_counts,
            explanation=(
                "Public report-type mix; does not establish causality for this unit. "
                "Product-code-only evidence is confidence-capped."
            ),
        ),
        ScoreComponent(
            name="recall_exposure",
            points=recall_points,
            max_points=config.recall_max,
            inputs={"recall_statuses": [recall.recall_status for recall in evidence.recall_records]},
            explanation="Manufacturer/model recall matches from openFDA.",
        ),
        ScoreComponent(
            name="maintenance_recurrence",
            points=maintenance_points,
            max_points=config.maintenance_max,
            inputs={
                "corrective_events_24m": evidence.maintenance_events_24m,
                "local_malfunction_count": asset.local_malfunction_count,
            },
            explanation="Fictional local maintenance recurrence for workshop use.",
        ),
    ]
    total = sum(component.points for component in components)
    action = (
        "retire"
        if total >= config.retire_threshold
        else "plan_replacement"
        if total >= config.replace_threshold
        else "maintain"
    )
    note = (
        "Public FDA evidence is missing or product-code-only; score is driven mainly by age and local mock maintenance."
        if evidence.confidence == "low"
        else "Public FDA evidence is model/product-level and is not unit attribution."
    )
    return RiskScore(
        asset_id=asset.asset_id,
        total=total,
        action=action,
        confidence=evidence.confidence,
        match_tier=evidence.match_tier,
        components=components,
        estimated_cost=asset.acquisition_cost,
        formula_version=config.formula_version,
        evidence_note=note,
    )
