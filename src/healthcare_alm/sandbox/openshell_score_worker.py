"""Pure-stdlib scoring worker shipped into an OpenShell sandbox over stdin."""

import json
import sys
from datetime import date


def clamp(value, maximum):
    return max(0, min(maximum, round(value)))


def component(name, points, maximum, inputs, explanation):
    return {
        "name": name,
        "points": points,
        "max_points": maximum,
        "inputs": inputs,
        "explanation": explanation,
    }


def score(payload):
    evidence = payload["evidence"]
    config = {
        "formula_version": "healthcare-alm-risk-v1",
        "retire_threshold": 70,
        "replace_threshold": 50,
        "age_max": 30,
        "trend_max": 25,
        "severity_max": 20,
        "recall_max": 15,
        "maintenance_max": 10,
        **payload.get("config", {}),
    }
    asset = evidence["asset"]
    as_of = date.fromisoformat(evidence["as_of_date"])
    install = date.fromisoformat(asset["install_date"])
    age_years = (as_of - install).days / 365.25
    age_ratio = age_years / asset["expected_service_years"]
    if age_ratio <= 0.5:
        age_points = 0
    elif age_ratio <= 1.0:
        age_points = clamp((age_ratio - 0.5) * 40, config["age_max"])
    else:
        age_points = clamp(20 + (age_ratio - 1.0) * 40, config["age_max"])

    recent = evidence.get("recent_maude_count", 0)
    older = evidence.get("older_maude_count", 0)
    if recent == 0:
        trend_points = 0
    elif older == 0:
        trend_points = clamp(10 + recent * 2, config["trend_max"])
    else:
        trend_points = clamp(max(0.0, (recent / older - 1.0) * 12.5), config["trend_max"])

    event_types = evidence.get("event_type_counts", {})
    event_total = sum(event_types.values())
    if event_types.get("Death", 0):
        severity_points = config["severity_max"]
    elif event_total:
        severity_points = clamp(
            event_types.get("Injury", 0) / event_total * 30 + min(event_total / 10 * 5, 5),
            config["severity_max"],
        )
    else:
        severity_points = 0

    if evidence["match_tier"] == "product_code_only":
        trend_points = min(trend_points, 5)
        severity_points = min(severity_points, 3)

    statuses = " ".join(record.get("recall_status", "").lower() for record in evidence.get("recall_records", []))
    if "open" in statuses or "ongoing" in statuses:
        recall_points = config["recall_max"]
    elif evidence.get("recall_records") and ("correct" in statuses or "classified" in statuses):
        recall_points = min(10, config["recall_max"])
    elif evidence.get("recall_records"):
        recall_points = min(5, config["recall_max"])
    else:
        recall_points = 0

    maintenance_points = clamp(
        evidence.get("maintenance_events_24m", 0) * 2 + min(asset.get("local_malfunction_count", 0), 5),
        config["maintenance_max"],
    )
    components = [
        component(
            "age_service_life",
            age_points,
            config["age_max"],
            {"age_years": round(age_years, 2), "expected_service_years": asset["expected_service_years"]},
            "Installed age relative to configured expected service life.",
        ),
        component(
            "maude_trend",
            trend_points,
            config["trend_max"],
            {"recent_count": recent, "older_count": older, "match_tier": evidence["match_tier"]},
            "Change in matched public MAUDE report counts; not an incidence rate. "
            "Product-code-only evidence is confidence-capped.",
        ),
        component(
            "event_severity_mix",
            severity_points,
            config["severity_max"],
            event_types,
            "Public report-type mix; does not establish causality for this unit. "
            "Product-code-only evidence is confidence-capped.",
        ),
        component(
            "recall_exposure",
            recall_points,
            config["recall_max"],
            {"recall_statuses": [record.get("recall_status", "") for record in evidence.get("recall_records", [])]},
            "Manufacturer/model recall matches from openFDA.",
        ),
        component(
            "maintenance_recurrence",
            maintenance_points,
            config["maintenance_max"],
            {
                "corrective_events_24m": evidence.get("maintenance_events_24m", 0),
                "local_malfunction_count": asset.get("local_malfunction_count", 0),
            },
            "Fictional local maintenance recurrence for workshop use.",
        ),
    ]
    total = sum(item["points"] for item in components)
    action = (
        "retire"
        if total >= config["retire_threshold"]
        else "plan_replacement"
        if total >= config["replace_threshold"]
        else "maintain"
    )
    note = (
        "Public FDA evidence is missing or product-code-only; score is driven mainly by age and local mock maintenance."
        if evidence["confidence"] == "low"
        else "Public FDA evidence is model/product-level and is not unit attribution."
    )
    return {
        "asset_id": asset["asset_id"],
        "total": total,
        "action": action,
        "confidence": evidence["confidence"],
        "match_tier": evidence["match_tier"],
        "components": components,
        "estimated_cost": str(asset["acquisition_cost"]),
        "formula_version": config["formula_version"],
        "evidence_note": note,
    }


if __name__ == "__main__":
    json.dump(score(json.load(sys.stdin)), sys.stdout)
