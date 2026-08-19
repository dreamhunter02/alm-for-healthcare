from decimal import Decimal

from healthcare_alm.models import RetirementPlan, RetirementPlanItem
from healthcare_alm.plotting.plot_utils import create_risk_chart


def test_risk_chart_creates_nonempty_html(tmp_path):
    plan = RetirementPlan(
        annual_budget=Decimal("120000"),
        current_phase_spend=Decimal("30000"),
        items=[
            RetirementPlanItem(
                asset_id="PUMP-001",
                action="retire",
                risk_score=82,
                estimated_cost=Decimal("30000"),
                phase="current_budget",
                evidence_confidence="high",
                rationale="Age and recurring maintenance",
            )
        ],
        current_phase=[],
        next_phase=[],
    )
    artifacts = create_risk_chart(plan, tmp_path)
    assert artifacts[0].path.exists()
    assert artifacts[0].path.stat().st_size > 100
    assert artifacts[0].media_type == "text/html"
