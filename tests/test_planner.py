from decimal import Decimal

from healthcare_alm.analysis.planner import build_retirement_plan
from healthcare_alm.models import RiskScore, ScoreComponent


def _score(asset_id, total, cost):
    return RiskScore(
        asset_id=asset_id,
        total=total,
        action="retire" if total >= 70 else "plan_replacement" if total >= 50 else "maintain",
        confidence="high",
        match_tier="manufacturer_model",
        components=[ScoreComponent(name="test", points=total, max_points=100, inputs={}, explanation="test")],
        estimated_cost=Decimal(cost),
    )


def test_budget_plan_never_exceeds_annual_budget():
    scores = [_score("A", 90, "70000"), _score("B", 80, "50000"), _score("C", 75, "60000")]
    plan = build_retirement_plan(scores, Decimal("120000"))
    assert sum(item.estimated_cost for item in plan.current_phase) <= Decimal("120000")
    assert [item.asset_id for item in plan.current_phase] == ["A", "B"]
    assert [item.asset_id for item in plan.next_phase] == ["C"]


def test_maintain_assets_are_not_charged_to_replacement_budget():
    plan = build_retirement_plan([_score("A", 20, "30000")], Decimal("1000"))
    assert plan.current_phase == []
    assert plan.items[0].phase == "monitor"
