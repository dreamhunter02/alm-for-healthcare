import json

import httpx

from healthcare_alm.fda.client import FDAClient
from healthcare_alm.fda.normalize import normalize_maude


def _write_maude_fixture(path):
    payload = {
        "meta": {"last_updated": "2026-07-31", "results": {"total": 2}},
        "results": [
            {
                "mdr_report_key": "1001",
                "report_number": "MDR-1001",
                "date_received": "20260110",
                "event_type": "Malfunction",
                "device": [
                    {
                        "manufacturer_d_name": "Acme Medical",
                        "brand_name": "FlowSafe",
                        "model_number": "FS-900",
                        "openfda": {
                            "device_name": "Pump, Infusion",
                            "device_class": "2",
                            "regulation_number": "880.5725",
                        },
                        "device_report_product_code": "FRN",
                    }
                ],
            },
            {
                "mdr_report_key": "1002",
                "report_number": "MDR-1002",
                "date_received": "20260211",
                "event_type": "Injury",
                "device": [
                    {
                        "manufacturer_d_name": "Acme Medical",
                        "brand_name": "FlowSafe",
                        "model_number": "FS-900",
                        "device_report_product_code": "FRN",
                    }
                ],
            },
        ],
    }
    path.write_text(json.dumps(payload))


def test_cached_maude_normalizes_and_deduplicates(tmp_path):
    _write_maude_fixture(tmp_path / "maude_frn.json")
    response = FDAClient(fixture_dir=tmp_path).fetch_maude("FRN", live=False)
    events = normalize_maude(response.results + response.results[:1], response.source_url)
    assert len(events) == 2
    assert len({event.report_number for event in events}) == len(events)
    assert all(event.product_code == "FRN" for event in events)
    assert all(event.source_url.startswith("https://api.fda.gov/device/event.json") for event in events)


def test_live_failure_uses_cache_and_marks_provenance(httpx_mock, tmp_path):
    _write_maude_fixture(tmp_path / "maude_frn.json")
    httpx_mock.add_exception(httpx.ConnectTimeout("timeout"))
    response = FDAClient(fixture_dir=tmp_path, retry_attempts=1).fetch_maude("FRN", live=True)
    assert response.provenance == "cached_fallback"
    assert response.results


def test_query_uses_product_code_and_limit(httpx_mock, tmp_path):
    httpx_mock.add_response(
        url="https://api.fda.gov/device/event.json?search=device.device_report_product_code%3AFRN&limit=1000",
        json={"meta": {"last_updated": "2026-07-31"}, "results": []},
    )
    response = FDAClient(fixture_dir=tmp_path, retry_attempts=1).fetch_maude("FRN", live=True)
    assert response.provenance == "live"
    assert response.results == []
