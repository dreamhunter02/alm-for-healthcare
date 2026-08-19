from typer.testing import CliRunner

from healthcare_alm.cli import app


def test_cli_has_workshop_commands():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("run", "serve", "serve-mcp", "refresh-fda", "validate"):
        assert command in result.stdout
