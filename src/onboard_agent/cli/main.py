"""Typer CLI: `onboard ingest`, `onboard ask`, `onboard serve-mcp`, `onboard eval`."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

import onboard_agent.cli._console_encoding  # noqa: F401  (import for its UTF-8 reconfigure side effect)
from onboard_agent.agent.loop import ask_onboarding_question
from onboard_agent.ingestion.pipeline import (
    RepoContext,
    get_or_ingest_repo_context,
    ingest_local_directory,
    ingest_repo,
)

app = typer.Typer(help="OnboardAgent: read-only onboarding Q&A for Python codebases.")
console = Console()


def _resolve_repo_context(repo_url: str | None, local_path: str | None) -> RepoContext:
    if local_path:
        return ingest_local_directory(Path(local_path))
    if repo_url:
        return get_or_ingest_repo_context(repo_url)
    console.print("[red]Provide a repo URL or --local-path[/red]")
    raise typer.Exit(code=1)


@app.command()
def ingest(
    repo_url: str | None = typer.Argument(
        None, help="Public GitHub repo URL, e.g. https://github.com/org/repo"
    ),
    local_path: str | None = typer.Option(
        None, "--local-path", help="Path to an already-checked-out repo (skips cloning)"
    ),
):
    """Clone and index a repo so `onboard ask` can answer questions about it."""
    if local_path:
        console.print(f"[bold]Ingesting[/bold] local path {local_path} ...")
        ctx = ingest_local_directory(Path(local_path))
    elif repo_url:
        console.print(f"[bold]Ingesting[/bold] {repo_url} ...")
        ctx = ingest_repo(repo_url)
    else:
        console.print("[red]Provide a repo URL or --local-path[/red]")
        raise typer.Exit(code=1)
    console.print(
        f"[green]Done.[/green] {len(ctx.chunks)} chunks indexed from "
        f"{ctx.org}/{ctx.repo}@{ctx.commit_sha[:12]}"
    )


@app.command()
def ask(
    question: str = typer.Argument(..., help="The onboarding question to ask"),
    repo_url: str | None = typer.Option(
        None, "--repo", help="Repo URL (auto-ingests if not cached)"
    ),
    local_path: str | None = typer.Option(
        None, "--local-path", help="Path to an already-checked-out repo (skips cloning)"
    ),
):
    """Ask a cited, grounded onboarding question about a repo."""
    ctx = _resolve_repo_context(repo_url, local_path)
    result = ask_onboarding_question(question, ctx)

    console.print(result.answer)
    console.print()
    if result.citations:
        console.print(f"[dim]Citations: {', '.join(result.citations)}[/dim]")
    if not result.verified:
        unverified = ", ".join(result.unverified_citations)
        console.print(f"[yellow]Warning: unverified citations: {unverified}[/yellow]")


@app.command("serve-mcp")
def serve_mcp(
    repo_url: str | None = typer.Option(None, "--repo", help="Public GitHub repo URL"),
    local_path: str | None = typer.Option(
        None, "--local-path", help="Path to an already-checked-out repo (skips cloning)"
    ),
):
    """Start the MCP server (stdio transport) scoped to one repo."""
    if local_path:
        os.environ["ONBOARD_AGENT_LOCAL_REPO_PATH"] = str(Path(local_path))
    elif repo_url:
        os.environ["ONBOARD_AGENT_REPO_URL"] = repo_url
    else:
        console.print("[red]Provide --repo or --local-path[/red]")
        raise typer.Exit(code=1)

    from onboard_agent.mcp_server.server import main as run_server

    run_server()


@app.command("eval")
def run_eval_command(
    fixtures_dir: str | None = typer.Option(
        None, "--fixtures", help="Directory of eval fixture YAML files (default: built-in set)"
    ),
    retrieval_only: bool = typer.Option(
        False, "--retrieval-only", help="Skip the answering agent; score retrieval recall only"
    ),
):
    """Run the eval harness and print a metrics table (see EVALS.md)."""
    from onboard_agent.evals.harness import run_evals

    report = run_evals(
        fixtures_dir=Path(fixtures_dir) if fixtures_dir else None, retrieval_only=retrieval_only
    )

    table = Table(title="OnboardAgent Evals")
    table.add_column("Repo")
    table.add_column("Retrieval Recall@K")
    table.add_column("Citation Groundedness")
    table.add_column("Refusal Accuracy")
    for row in report.rows:
        table.add_row(
            row.repo_label,
            f"{row.retrieval_recall:.0%}",
            "n/a" if row.citation_groundedness is None else f"{row.citation_groundedness:.0%}",
            "n/a" if row.refusal_accuracy is None else f"{row.refusal_accuracy:.0%}",
        )
    console.print(table)
    report.write_markdown(Path("EVALS.md"))


if __name__ == "__main__":
    app()
