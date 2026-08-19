import json
import sys

from healthcare_alm.sandbox.local import LocalSandboxRunner
from tests.test_scoring import _high_risk_evidence


def test_local_sandbox_uses_empty_environment_and_captures_result(tmp_path):
    payload = {"asset_id": "PUMP-001", "score": 72}
    result = LocalSandboxRunner(timeout_seconds=10).run_score(payload, tmp_path)
    assert result.provider == "local_subprocess"
    assert result.exit_code == 0
    assert result.artifacts[0].sha256
    assert result.environment_keys == []


def test_local_sandbox_times_out(tmp_path):
    result = LocalSandboxRunner(timeout_seconds=0.01).run_command(
        [sys.executable, "-c", "import time; time.sleep(2)"], tmp_path
    )
    assert result.status == "timeout"


def test_local_sandbox_executes_versioned_scoring(tmp_path):
    payload = {"evidence": _high_risk_evidence().model_dump(mode="json"), "config": {}}
    result = LocalSandboxRunner(timeout_seconds=10).run_score(payload, tmp_path)
    scored = json.loads(result.artifacts[0].path.read_text())
    assert scored["action"] == "retire"
    assert scored["formula_version"] == "healthcare-alm-risk-v1"
