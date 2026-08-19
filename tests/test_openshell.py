import json
import subprocess

from healthcare_alm.analysis.scoring import score_asset
from healthcare_alm.models import ScoreConfig
from healthcare_alm.sandbox.openshell import OpenShellSandboxRunner, create_sandbox_runner, score_worker_source
from tests.test_scoring import _high_risk_evidence


def test_openshell_worker_matches_host_scoring_contract():
    evidence = _high_risk_evidence()
    payload = {"evidence": evidence.model_dump(mode="json"), "config": {}}

    completed = subprocess.run(
        ["python3", "-c", score_worker_source()],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(completed.stdout) == score_asset(evidence, ScoreConfig()).model_dump(mode="json")


def test_openshell_runner_does_not_forward_host_environment(monkeypatch, tmp_path):
    expected = score_asset(_high_risk_evidence(), ScoreConfig()).model_dump(mode="json")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(expected), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = OpenShellSandboxRunner("alm-scoring", executable="openshell")
    result = runner.run_score({"evidence": _high_risk_evidence().model_dump(mode="json"), "config": {}}, tmp_path)

    assert captured["command"][:6] == ["openshell", "sandbox", "exec", "-n", "alm-scoring", "--timeout"]
    assert "--env" not in captured["command"]
    assert "env" not in captured["kwargs"]
    assert result.provider == "openshell"
    assert result.artifacts[0].path.exists()


def test_auto_runner_uses_openshell_only_when_cli_and_target_are_configured(monkeypatch):
    monkeypatch.setenv("OPENSHELL_SANDBOX", "alm-scoring")
    monkeypatch.setattr(OpenShellSandboxRunner, "available", classmethod(lambda cls, executable="openshell": True))

    runner = create_sandbox_runner("auto")

    assert isinstance(runner, OpenShellSandboxRunner)
    assert runner.sandbox_name == "alm-scoring"
