import json
from pathlib import Path


def test_cached_workshop_meets_declared_acceptance_contract(workflow_result):
    expected = json.loads(Path("evaluation/expected_outcomes.json").read_text())
    scores = {score.asset_id: score for score in workflow_result.scores}

    pump_009 = expected["expectations"][0]
    assert scores[pump_009["asset_id"]].action == pump_009["action"]
    assert scores[pump_009["asset_id"]].total >= pump_009["minimum_score"]
    assert scores[pump_009["asset_id"]].match_tier == pump_009["match_tier"]

    pump_011 = expected["expectations"][1]
    assert scores[pump_011["asset_id"]].action == pump_011["action"]
    assert scores[pump_011["asset_id"]].total <= pump_011["maximum_score"]
    assert len(workflow_result.plan.items) == 12
    assert len(workflow_result.stage_events) == 7
    assert all(not evidence.unit_attribution for evidence in workflow_result.evidence)
