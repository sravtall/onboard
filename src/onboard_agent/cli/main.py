"""Typer CLI: `onboard ingest`, `onboard ask`, `onboard serve-mcp`, `onboard eval`."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

import onboard_agent.cli._console_encoding  # noqa: F401  (import for its UTF-8 reconfigure side effect)
from onboard_agent.agent.loop import ask_onboarding_question
from onboard_agent.agent.overview import generate_overview
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


@app.command()
def overview(
    repo_url: str | None = typer.Option(
        None, "--repo", help="Repo URL (auto-ingests if not cached)"
    ),
    local_path: str | None = typer.Option(
        None, "--local-path", help="Path to an already-checked-out repo (skips cloning)"
    ),
    focus: str | None = typer.Option(
        None, "--focus", help="Area to emphasize, e.g. 'the authentication flow'"
    ),
):
    """Generate a cited onboarding overview of a repo (architecture, key modules, how to run)."""
    ctx = _resolve_repo_context(repo_url, local_path)
    result = generate_overview(ctx, focus=focus)

    console.print("[bold]Architecture[/bold]")
    console.print(result.architecture_summary)
    console.print()
    console.print("[bold]Key modules[/bold]")
    for section in result.key_modules:
        console.print(f"[cyan]{section.heading}[/cyan]")
        console.print(section.content)
        console.print()
    console.print("[bold]Directory map[/bold]")
    console.print(result.directory_map)
    console.print()
    console.print("[bold]Entry points[/bold]")
    for entry in result.entry_points:
        console.print(f"- {entry}")
    console.print()
    console.print("[bold]How to run and test[/bold]")
    console.print(result.how_to_run_and_test)
    console.print()
    console.print("[bold]Where to start[/bold]")
    console.print(result.where_to_start)
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
    write_report: bool = typer.Option(
        False,
        "--write-report",
        help="Overwrite docs/EVALS.md with a bare metrics table (default: print only). "
        "docs/EVALS.md normally carries hand-written analysis alongside the numbers -- "
        "this flag replaces all of it, so it's opt-in rather than a side effect of every run.",
    ),
):
    """Run the eval harness and print a metrics table (see docs/EVALS.md)."""
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
    if write_report:
        report.write_markdown(Path("docs/EVALS.md"))
        console.print("[dim]Wrote docs/EVALS.md (overwrote any hand-written analysis).[/dim]")


if __name__ == "__main__":
    app()
