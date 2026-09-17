"""Phase 4 exit criteria: the CLI answers a question about a real (fixture) repo with
citations, using --local-path to avoid a network clone in tests."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from onboard_agent.cli.main import app
from onboard_agent.config import has_api_key

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "tiny_repo"

runner = CliRunner()


def test_ingest_local_path_reports_chunk_count():
    result = runner.invoke(app, ["ingest", "--local-path", str(FIXTURE_REPO)])
    assert result.exit_code == 0, result.output
    assert "chunks indexed" in result.output


def test_ingest_requires_a_url_or_local_path():
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code != 0


@pytest.mark.skipif(not has_api_key(), reason="ANTHROPIC_API_KEY not set")
def test_ask_over_cli_prints_a_cited_answer():
    result = runner.invoke(
        app,
        ["ask", "How do I register a new user?", "--local-path", str(FIXTURE_REPO)],
    )
    assert result.exit_code == 0, result.output
    assert "classes_and_methods.py" in result.output
