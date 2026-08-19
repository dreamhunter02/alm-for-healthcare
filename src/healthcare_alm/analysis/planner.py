from __future__ import annotations

from decimal import Decimal

from healthcare_alm.models import RetirementPlan, RetirementPlanItem, RiskScore


def _item(score: RiskScore, phase: str) -> RetirementPlanItem:
    top = sorted(score.components, key=lambda component: component.points, reverse=True)[:2]
    rationale = "; ".join(f"{component.name}: {component.points}/{component.max_points}" for component in top)
    return RetirementPlanItem(
        asset_id=score.asset_id,
        action=score.action,
        risk_score=score.total,
        estimated_cost=score.estimated_cost,
        phase=phase,
        evidence_confidence=score.confidence,
        rationale=rationale,
    )


def build_retirement_plan(scores: list[RiskScore], annual_budget: Decimal) -> RetirementPlan:
    current: list[RetirementPlanItem] = []
    later: list[RetirementPlanItem] = []
    monitor: list[RetirementPlanItem] = []
    spend = Decimal("0")
    for score in sorted(scores, key=lambda value: (-value.total, value.asset_id)):
        if score.action == "maintain":
            monitor.append(_item(score, "monitor"))
        elif spend + score.estimated_cost <= annual_budget:
            current.append(_item(score, "current_budget"))
            spend += score.estimated_cost
        else:
            later.append(_item(score, "next_horizon"))
    items = current + later + monitor
    return RetirementPlan(
        annual_budget=annual_budget,
        current_phase_spend=spend,
        items=items,
        current_phase=current,
        next_phase=later,
    )
