from healthcare_alm.fda.client import FDAClient
from healthcare_alm.mcp.recall_server import RecallService, create_mcp_server


def test_recall_service_returns_model_grounded_matches():
    service = RecallService(FDAClient(fixture_dir="data/fixtures"))

    result = service.search("FRN", manufacturer="Zyno Medical LLC", model="Z-800F")

    assert result.status == "available_matches"
    assert result.records
    assert all(record.source_url.startswith("https://api.fda.gov/device/recall.json") for record in result.records)


def test_recall_service_distinguishes_no_match_from_unavailable():
    service = RecallService(FDAClient(fixture_dir="data/fixtures"))

    result = service.search("FRN", manufacturer="Not A Real Manufacturer", model="NOPE")

    assert result.status == "available_no_matches"
    assert result.records == []


def test_fastmcp_exposes_recall_tool():
    server = create_mcp_server(FDAClient(fixture_dir="data/fixtures"))

    assert server.name == "healthcare-alm-regulatory-grounding"
