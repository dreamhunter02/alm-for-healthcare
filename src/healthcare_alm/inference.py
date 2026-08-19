from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

import httpx

INFERENCE_HUB_BASE_URL = "https://integrate.api.nvidia.com/v1/"


def resolve_ultra_model(model_ids: list[str]) -> str:
    aliases = [
        model_id
        for model_id in model_ids
        if model_id.lower().replace("_", "-").rstrip("/").endswith(
            ("nemotron-3-ultra-550b-a55b", "nemotron-3-ultra")
        )
        and "eval" not in model_id.lower()
    ]
    if not aliases:
        raise RuntimeError("Nemotron Ultra is not available from the configured Inference Hub account")
    preferred = [model_id for model_id in aliases if model_id.lower().endswith("nemotron-3-ultra-550b-a55b")]
    if preferred:
        return sorted(preferred)[0]
    if len(aliases) > 1:
        non_quantized = [model_id for model_id in aliases if not model_id.lower().endswith("-nvfp4")]
        if len(non_quantized) == 1:
            return non_quantized[0]
        raise RuntimeError(f"Nemotron Ultra model resolution is ambiguous: {sorted(aliases)}")
    return aliases[0]


@dataclass(frozen=True)
class InferenceVerification:
    model_id: str
    completion_ok: bool
    tool_call_ok: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class InferenceHubClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = INFERENCE_HUB_BASE_URL,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=180,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post("chat/completions", json=payload)
        response.raise_for_status()
        return response.json()

    def verify(self, model_id: str | None = None) -> InferenceVerification:
        models_response = self._client.get("models")
        models_response.raise_for_status()
        model_ids = [item["id"] for item in models_response.json().get("data", [])]
        if model_id is None:
            model_id = resolve_ultra_model(model_ids)
        elif model_id not in model_ids:
            raise RuntimeError(f"Configured model {model_id!r} is not available from the configured endpoint")

        completion = self._post_chat(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": "Reply with exactly READY and nothing else."}],
                "max_tokens": 32,
                "temperature": 0,
            }
        )
        content = completion["choices"][0]["message"].get("content") or ""
        completion_ok = content.strip() == "READY"
        if not completion_ok:
            raise RuntimeError(f"Nemotron Ultra completion smoke test returned {content!r}, expected 'READY'")

        tool = {
            "type": "function",
            "function": {
                "name": "get_asset",
                "description": "Look up one fictional hospital asset.",
                "parameters": {
                    "type": "object",
                    "properties": {"asset_id": {"type": "string"}},
                    "required": ["asset_id"],
                },
            },
        }
        tool_response = self._post_chat(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": "Use get_asset to look up PUMP-009."}],
                "tools": [tool],
                "tool_choice": {"type": "function", "function": {"name": "get_asset"}},
                "max_tokens": 256,
                "temperature": 0,
            }
        )
        calls = tool_response["choices"][0]["message"].get("tool_calls") or []
        if len(calls) != 1:
            raise RuntimeError(f"Nemotron Ultra returned {len(calls)} tool calls, expected exactly one")
        function = calls[0].get("function", {})
        try:
            arguments = json.loads(function.get("arguments", "{}"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("Nemotron Ultra returned malformed tool arguments") from exc
        tool_call_ok = function.get("name") == "get_asset" and arguments == {"asset_id": "PUMP-009"}
        if not tool_call_ok:
            raise RuntimeError(
                f"Nemotron Ultra returned an unexpected tool call: {function.get('name')!r} {arguments!r}"
            )
        return InferenceVerification(model_id=model_id, completion_ok=True, tool_call_ok=True)
