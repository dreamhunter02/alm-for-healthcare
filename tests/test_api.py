from fastapi.testclient import TestClient

from healthcare_alm.api import DemoService, create_app


def test_api_serves_demo_data_and_dashboard(workflow_result):
    service = DemoService()
    service.latest = workflow_result
    client = TestClient(create_app(service))

    assert client.get("/health").json()["status"] == "ok"
    assert len(client.get("/api/assets").json()) == 12
    assert client.get("/api/plan").json()["items"]
    assert client.get("/api/audit").json()["trace_id"] == workflow_result.trace_id
    page = client.get("/")
    assert page.status_code == 200
    assert "Medical Device Retirement Command Center" in page.text


def test_demo_run_endpoint_accepts_budget(monkeypatch, workflow_result):
    service = DemoService()
    monkeypatch.setattr(service, "run", lambda request: workflow_result)
    client = TestClient(create_app(service))

    response = client.post("/api/demo/run", json={"budget": 80000})

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
