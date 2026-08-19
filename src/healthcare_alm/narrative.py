from __future__ import annotations

import os

import httpx

from healthcare_alm.models import WorkflowResult


class NarrativeGenerator:
    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = os.environ.get("NVIDIA_API_KEY", "") if api_key is None else api_key
        self.client = client or httpx.Client(timeout=45)
        self.model = model or os.environ.get("NVIDIA_MODEL_NAME", "")
        configured_base_url = base_url or os.environ.get("NVIDIA_API_BASE_URL", "")
        self.endpoint = f"{configured_base_url.rstrip('/')}/chat/completions" if configured_base_url else ""

    @staticmethod
    def _fallback(result: WorkflowResult) -> str:
        ranked = sorted(result.scores, key=lambda score: (-score.total, score.asset_id))
        lead = ranked[0]
        return (
            f"Prioritize {lead.asset_id}: score {lead.total}/100, recommendation {lead.action.replace('_', ' ')}. "
            f"Current budget covers {len(result.plan.current_phase)} asset(s) "
            f"at ${result.plan.current_phase_spend:,.0f}. "
            "Public FDA evidence is model/product-level only; route every recommendation through clinical engineering "
            "and human review."
        )

    def generate(self, result: WorkflowResult) -> str:
        if not self.api_key or not self.model or not self.endpoint:
            return self._fallback(result)
        scores = [
            {
                "asset_id": score.asset_id,
                "score": score.total,
                "action": score.action,
                "confidence": score.confidence,
                "top_components": [
                    {"name": component.name, "points": component.points}
                    for component in sorted(score.components, key=lambda item: item.points, reverse=True)[:3]
                ],
            }
            for score in sorted(result.scores, key=lambda item: -item.total)[:5]
        ]
        prompt = (
            "Write a concise clinical-engineering retirement briefing from this ranked evidence. "
            "State that public FDA signals are model/product-level, are not incidence rates, do not establish "
            "unit causality, and require human review. Do not invent facts.\n"
            f"Budget: {result.plan.annual_budget}; ranked evidence: {scores}"
        )
        try:
            response = self.client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are an auditable clinical engineering planning assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 450,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            return self._fallback(result)
