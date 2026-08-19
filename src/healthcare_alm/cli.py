from __future__ import annotations

import json
import tempfile
from decimal import Decimal
from pathlib import Path

import typer

from healthcare_alm.api import app as api_app
from healthcare_alm.fda.client import FDAClient
from healthcare_alm.models import RetirementRequest
from healthcare_alm.narrative import NarrativeGenerator
from healthcare_alm.orchestrator.graph import STAGES, run_workflow
from healthcare_alm.reporting.audit import build_audit_bundle

app = typer.Typer(help="Medical-device retirement planning workshop demo.", no_args_is_help=True)


@app.command()
def run(
    budget: float = typer.Option(120000, help="Annual replacement budget."),
    output: Path = typer.Option(Path("output/latest"), help="Artifact directory."),
    live_fda: bool = typer.Option(False, help="Use live openFDA with cached fallback."),
    sandbox: str = typer.Option("auto", help="auto, local, or openshell."),
    use_nim: bool = typer.Option(False, help="Generate briefing with NVIDIA-hosted NIM."),
) -> None:
    """Run all seven agents and write the audit bundle."""
    request = RetirementRequest(
        budget=Decimal(str(budget)),
        live_fda=live_fda,
        sandbox_provider=sandbox,
        output_dir=output,
    )
    result = run_workflow(request)
    artifacts = build_audit_bundle(result, output / "bundle")
    narrative = NarrativeGenerator(api_key=None if use_nim else "").generate(result)
    typer.echo(narrative)
    typer.echo(f"Trace: {result.trace_id}")
    typer.echo(f"Artifacts: {len(artifacts)} in {output / 'bundle'}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
) -> None:
    """Serve the browser workshop dashboard and JSON API."""
    import uvicorn

    uvicorn.run(api_app, host=host, port=port)


@app.command("serve-mcp")
def serve_mcp() -> None:
    """Expose recall grounding as a stdio MCP server."""
    from healthcare_alm.mcp.recall_server import mcp

    mcp.run()


@app.command("refresh-fda")
def refresh_fda(product_code: str = "FRN", fixture_dir: Path = Path("data/fixtures")) -> None:
    """Refresh openFDA fixture snapshots; refuses to replace cache on network fallback."""
    client = FDAClient(fixture_dir=fixture_dir)
    for kind, response in (
        ("maude", client.fetch_maude(product_code, live=True)),
        ("recalls", client.fetch_recalls(product_code, live=True)),
    ):
        if response.provenance != "live":
            raise typer.BadParameter(f"{kind} refresh did not return live data; existing cache preserved")
        path = fixture_dir / f"{kind}_{product_code.lower()}.json"
        path.write_text(
            json.dumps(
                {
                    "meta": {"last_updated": response.last_updated, "disclaimer": response.disclaimer},
                    "results": response.results,
                },
                indent=2,
            )
        )
        typer.echo(f"Updated {path}")


@app.command()
def validate() -> None:
    """Run a cached end-to-end workshop smoke test."""
    with tempfile.TemporaryDirectory(prefix="healthcare-alm-validate-") as temporary:
        result = run_workflow(RetirementRequest(output_dir=Path(temporary)))
        actual = [event.stage for event in result.stage_events]
        actions = {score.action for score in result.scores}
        if actual != STAGES or not {"retire", "maintain"} <= actions:
            raise typer.Exit(code=1)
        typer.echo(f"PASS: {len(result.plan.items)} assets, 7 stages, retire + maintain examples")


if __name__ == "__main__":
    app()
