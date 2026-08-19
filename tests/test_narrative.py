import httpx

from healthcare_alm.narrative import NarrativeGenerator


def test_nim_narrative_uses_chat_completions_contract(workflow_result):
    captured = {}

    def handler(request):
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "Prioritize PUMP-009."}}]})

    generator = NarrativeGenerator(
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        model="test-model",
        base_url="https://llm.example.test/v1",
    )

    narrative = generator.generate(workflow_result)

    assert narrative == "Prioritize PUMP-009."
    assert captured["authorization"] == "Bearer test-key"
    assert "public FDA signals" in captured["body"]


def test_narrative_has_offline_fallback(workflow_result):
    narrative = NarrativeGenerator(api_key="").generate(workflow_result)

    assert "PUMP-009" in narrative
    assert "human review" in narrative.lower()
