# SPDX-FileCopyrightText: Copyright (c) 2023-2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
from pathlib import Path

import plotly.graph_objects as go

from healthcare_alm.models import ArtifactRef, RetirementPlan


def _artifact(path: Path, artifact_id: str) -> ArtifactRef:
    data = path.read_bytes()
    return ArtifactRef(
        artifact_id=artifact_id,
        path=path,
        media_type="text/html",
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


def create_risk_chart(plan: RetirementPlan, output_dir: Path) -> list[ArtifactRef]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ordered = sorted(plan.items, key=lambda item: item.risk_score)
    colors = {"retire": "#d32f2f", "plan_replacement": "#f9a825", "maintain": "#2e7d32"}
    figure = go.Figure(
        go.Bar(
            x=[item.risk_score for item in ordered],
            y=[item.asset_id for item in ordered],
            orientation="h",
            marker_color=[colors[item.action] for item in ordered],
            text=[item.action.replace("_", " ").title() for item in ordered],
        )
    )
    figure.update_layout(
        title="Infusion Pump Retirement Risk",
        xaxis_title="Explainable risk score (0-100)",
        yaxis_title="Hospital asset",
        template="plotly_white",
    )
    path = output_dir / "risk_ranking.html"
    figure.write_html(path, include_plotlyjs=True, full_html=True)
    return [_artifact(path, "risk-ranking")]
