from __future__ import annotations

import csv
import hashlib
import html
import json
from pathlib import Path

from healthcare_alm.models import OPENFDA_DISCLAIMER, ArtifactRef, WorkflowResult
from healthcare_alm.plotting.plot_utils import create_risk_chart


def _artifact(path: Path, artifact_id: str, media_type: str) -> ArtifactRef:
    data = path.read_bytes()
    return ArtifactRef(
        artifact_id=artifact_id,
        path=path,
        media_type=media_type,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


def _markdown(result: WorkflowResult) -> str:
    lines = [
        "# Medical Device Retirement Audit Report",
        "",
        f"Trace ID: `{result.trace_id}`",
        f"FDA provenance: `{json.dumps(result.fda_provenance, sort_keys=True)}`",
        f"Sandbox provider: `{result.sandbox_provider}`",
        "",
        "## Ranked plan",
        "",
        "| Asset | Score | Recommendation | Phase | Cost | Evidence confidence |",
        "|---|---:|---|---|---:|---|",
    ]
    for item in result.plan.items:
        lines.append(
            f"| {item.asset_id} | {item.risk_score} | {item.action} | {item.phase} | "
            f"${item.estimated_cost:,.0f} | {item.evidence_confidence} |"
        )
    lines.extend(
        [
            "",
            "## Decision trail",
            "",
            *[
                f"- `{event.stage}` — {event.message} ({event.input_count} → {event.output_count})"
                for event in result.stage_events
            ],
            "",
            "## Safety boundary",
            "",
            f"{OPENFDA_DISCLAIMER} Public reports are not incidence rates. Recommendations require human review.",
            "",
        ]
    )
    return "\n".join(lines)


def build_audit_bundle(result: WorkflowResult, output_dir: Path | str) -> list[ArtifactRef]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    artifacts: list[ArtifactRef] = []

    audit_json = output / "audit.json"
    audit_json.write_text(result.model_dump_json(indent=2))
    artifacts.append(_artifact(audit_json, "audit-json", "application/json"))

    csv_path = output / "retirement_plan.csv"
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "asset_id",
                "risk_score",
                "recommendation",
                "phase",
                "estimated_cost",
                "evidence_confidence",
                "rationale",
            ],
        )
        writer.writeheader()
        for item in result.plan.items:
            writer.writerow(
                {
                    "asset_id": item.asset_id,
                    "risk_score": item.risk_score,
                    "recommendation": item.action,
                    "phase": item.phase,
                    "estimated_cost": item.estimated_cost,
                    "evidence_confidence": item.evidence_confidence,
                    "rationale": item.rationale,
                }
            )
    artifacts.append(_artifact(csv_path, "retirement-plan-csv", "text/csv"))

    markdown = _markdown(result)
    markdown_path = output / "audit_report.md"
    markdown_path.write_text(markdown)
    artifacts.append(_artifact(markdown_path, "audit-markdown", "text/markdown"))

    html_path = output / "audit_report.html"
    html_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Medical Device Retirement Audit</title>"
        "<style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 24px;line-height:1.5}"
        "pre{white-space:pre-wrap;background:#f4f4f4;padding:24px;border-left:5px solid #76b900}</style></head>"
        f"<body><pre>{html.escape(markdown)}</pre></body></html>"
    )
    artifacts.append(_artifact(html_path, "audit-html", "text/html"))
    artifacts.extend(create_risk_chart(result.plan, output))

    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "trace_id": result.trace_id,
                "formula_versions": sorted({score.formula_version for score in result.scores}),
                "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
            },
            indent=2,
            sort_keys=True,
        )
    )
    artifacts.append(_artifact(manifest_path, "manifest", "application/json"))
    return artifacts
