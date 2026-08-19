import csv
import json

from healthcare_alm.reporting.audit import build_audit_bundle


def test_audit_bundle_is_complete_and_hash_verifiable(workflow_result, tmp_path):
    bundle = build_audit_bundle(workflow_result, tmp_path)

    artifact_ids = {artifact.artifact_id for artifact in bundle}
    assert artifact_ids >= {
        "audit-json",
        "retirement-plan-csv",
        "audit-markdown",
        "audit-html",
        "risk-ranking",
        "manifest",
    }
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["trace_id"] == workflow_result.trace_id
    assert all(item["sha256"] for item in manifest["artifacts"])

    with (tmp_path / "retirement_plan.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 12
    report = (tmp_path / "audit_report.md").read_text()
    assert workflow_result.trace_id in report
    assert "not incidence rates" in report
