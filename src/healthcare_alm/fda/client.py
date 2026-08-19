from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from healthcare_alm.models import FDAResponse


class FDAClient:
    """Small openFDA client with deterministic cached fallback."""

    EVENT_ENDPOINT = "https://api.fda.gov/device/event.json"
    RECALL_ENDPOINT = "https://api.fda.gov/device/recall.json"

    def __init__(
        self,
        fixture_dir: Path | str = Path("data/fixtures"),
        timeout_seconds: float = 15.0,
        retry_attempts: int = 3,
        client: httpx.Client | None = None,
    ) -> None:
        self.fixture_dir = Path(fixture_dir)
        self.retry_attempts = max(1, retry_attempts)
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def fetch_maude(self, product_code: str, live: bool = False) -> FDAResponse:
        params = {"search": f"device.device_report_product_code:{product_code.upper()}", "limit": 1000}
        return self._fetch(
            endpoint=self.EVENT_ENDPOINT,
            params=params,
            fixture_name=f"maude_{product_code.lower()}.json",
            product_code=product_code,
            live=live,
        )

    def fetch_recalls(self, product_code: str, live: bool = False) -> FDAResponse:
        params = {"search": f"product_code:{product_code.upper()}", "limit": 1000}
        return self._fetch(
            endpoint=self.RECALL_ENDPOINT,
            params=params,
            fixture_name=f"recalls_{product_code.lower()}.json",
            product_code=product_code,
            live=live,
        )

    def _fetch(
        self,
        endpoint: str,
        params: dict[str, Any],
        fixture_name: str,
        product_code: str,
        live: bool,
    ) -> FDAResponse:
        source_url = f"{endpoint}?{urlencode(params)}"
        if live:
            for attempt in range(self.retry_attempts):
                try:
                    response = self.client.get(endpoint, params=params)
                    response.raise_for_status()
                    return self._to_response(response.json(), endpoint, product_code, str(response.url), "live")
                except (httpx.HTTPError, ValueError):
                    if attempt + 1 < self.retry_attempts:
                        time.sleep(min(0.25 * (2**attempt), 1.0))
        payload = self._load_fixture(fixture_name)
        provenance = "cached_fallback" if live else "cached"
        return self._to_response(payload, endpoint, product_code, source_url, provenance)

    def _load_fixture(self, fixture_name: str) -> dict[str, Any]:
        fixture_path = self.fixture_dir / fixture_name
        if not fixture_path.exists():
            raise FileNotFoundError(f"openFDA fixture not found: {fixture_path}")
        return json.loads(fixture_path.read_text())

    @staticmethod
    def _to_response(
        payload: dict[str, Any], endpoint: str, product_code: str, source_url: str, provenance: str
    ) -> FDAResponse:
        meta = payload.get("meta", {})
        return FDAResponse(
            endpoint=endpoint,
            product_code=product_code.upper(),
            source_url=source_url,
            provenance=provenance,
            last_updated=meta.get("last_updated"),
            results=payload.get("results", []),
            disclaimer=meta.get("disclaimer") or FDAResponse.model_fields["disclaimer"].default,
        )
