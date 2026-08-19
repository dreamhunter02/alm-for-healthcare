import json

import httpx
import pytest

from healthcare_alm.inference import InferenceHubClient, resolve_ultra_model


def test_resolve_ultra_model_accepts_inference_hub_alias():
    assert resolve_ultra_model(["nvidia/nvidia/nemotron-3-ultra", "other/model"]) == (
        "nvidia/nvidia/nemotron-3-ultra"
    )


def test_resolve_ultra_model_fails_closed_when_ultra_is_unavailable():
    with pytest.raises(RuntimeError, match="Nemotron Ultra is not available"):
        resolve_ultra_model(["nvidia/nvidia/nemotron-3-super"])


def test_smoke_test_requires_completion_and_structured_tool_call():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "nvidia/nvidia/nemotron-3-ultra"}]})
        payload = json.loads(request.content)
        requests.append(payload)
        if payload.get("tools"):
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call-1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_asset",
                                            "arguments": '{"asset_id":"PUMP-009"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": "READY"}}]})

    client = InferenceHubClient(
        api_key="secret-value",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test/v1/"),
    )

    result = client.verify()

    assert result.model_id == "nvidia/nvidia/nemotron-3-ultra"
    assert result.completion_ok is True
    assert result.tool_call_ok is True
    assert len(requests) == 2
    assert requests[1]["tool_choice"]["function"]["name"] == "get_asset"
    assert "secret-value" not in json.dumps(result.as_dict())

