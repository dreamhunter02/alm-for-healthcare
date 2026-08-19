from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from healthcare_alm.fda.client import FDAClient
from healthcare_alm.fda.normalize import normalize_recalls, normalize_text
from healthcare_alm.models import RecallRecord, RecallSearchResult


def _manufacturer_matches(query: str, candidate: str) -> bool:
    query_text = normalize_text(query)
    candidate_text = normalize_text(candidate)
    return query_text == candidate_text or bool(
        query_text and candidate_text and query_text.split()[0] == candidate_text.split()[0]
    )


def _filter_records(records: list[RecallRecord], manufacturer: str | None, model: str | None) -> list[RecallRecord]:
    matches = records
    if manufacturer:
        matches = [record for record in matches if _manufacturer_matches(manufacturer, record.manufacturer)]
    if model:
        model_text = normalize_text(model)
        matches = [
            record
            for record in matches
            if model_text in normalize_text(f"{record.model_number} {record.product_description}")
        ]
    return matches


class RecallService:
    """Regulatory grounding service; absence and unavailability are different states."""

    def __init__(self, client: FDAClient | None = None, live: bool = False) -> None:
        self.client = client or FDAClient()
        self.live = live

    def search(
        self,
        product_code: str,
        manufacturer: str | None = None,
        model: str | None = None,
    ) -> RecallSearchResult:
        try:
            response = self.client.fetch_recalls(product_code, live=self.live)
            records = normalize_recalls(response.results, response.source_url)
            matches = _filter_records(records, manufacturer, model)
            status = "available_matches" if matches else "available_no_matches"
            return RecallSearchResult(
                status=status,
                records=matches,
                source_url=response.source_url,
                provenance=response.provenance,
                message=f"Found {len(matches)} matching recall record(s).",
                disclaimer=response.disclaimer,
            )
        except (FileNotFoundError, OSError, ValueError) as error:
            return RecallSearchResult(
                status="unavailable",
                provenance="unavailable",
                message=f"Recall evidence unavailable: {error}",
            )


def create_mcp_server(client: FDAClient | None = None, live: bool = False) -> FastMCP:
    service = RecallService(client=client, live=live)
    server = FastMCP("healthcare-alm-regulatory-grounding")

    @server.tool()
    def search_device_recalls(
        product_code: str,
        manufacturer: str | None = None,
        model: str | None = None,
    ) -> dict:
        """Search openFDA recalls and return model-grounded regulatory evidence."""
        return service.search(product_code, manufacturer, model).model_dump(mode="json")

    return server


mcp = create_mcp_server()


if __name__ == "__main__":
    mcp.run()
