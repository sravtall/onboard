"""MCP server for OnboardAgent: read-only tools over a single ingested repo, resolved once at
startup from ONBOARD_AGENT_REPO_URL. Every tool here is a thin adapter over src/onboard_agent/
tools/ and agent/loop.py — never a reimplementation (see CLAUDE.md's architecture invariant)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server import MCPServer

from onboard_agent.agent.loop import ask_onboarding_question as _ask_onboarding_question_impl
from onboard_agent.ingestion.pipeline import (
    RepoContext,
    get_or_ingest_repo_context,
    ingest_local_directory,
)
from onboard_agent.tools.list_structure import list_structure as _list_structure_impl
from onboard_agent.tools.read_file import read_file as _read_file_impl
from onboard_agent.tools.schemas import ListStructureInput, ReadFileInput, SearchCodebaseInput
from onboard_agent.tools.search_codebase import search_codebase as _search_codebase_impl

mcp = MCPServer("onboard-agent")

_repo_context: RepoContext | None = None


def _get_repo_context() -> RepoContext:
    global _repo_context
    if _repo_context is None:
        local_path = os.environ.get("ONBOARD_AGENT_LOCAL_REPO_PATH")
        if local_path:
            _repo_context = ingest_local_directory(Path(local_path))
            return _repo_context

        url = os.environ.get("ONBOARD_AGENT_REPO_URL")
        if not url:
            raise RuntimeError(
                "Neither ONBOARD_AGENT_REPO_URL nor ONBOARD_AGENT_LOCAL_REPO_PATH is set. "
                "Point one of them at a repo before starting this MCP server (see README.md)."
            )
        _repo_context = get_or_ingest_repo_context(url)
    return _repo_context


@mcp.tool()
def search_codebase(query: str, top_k: int = 5) -> str:
    """Search the ingested codebase with hybrid semantic + keyword search.

    Returns matching code chunks as JSON, each carrying a `citation` field of the form
    `path/to/file.py:START-END`.
    """
    result = _search_codebase_impl(
        SearchCodebaseInput(query=query, top_k=top_k), _get_repo_context()
    )
    return result.model_dump_json()


@mcp.tool()
def read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    """Read an exact line range (or the whole file) from the ingested repo.

    `path` must be relative to the repo root; paths that escape the repo root are rejected.
    """
    result = _read_file_impl(
        ReadFileInput(path=path, start_line=start_line, end_line=end_line), _get_repo_context()
    )
    return result.model_dump_json()


@mcp.tool()
def list_structure(path: str = ".") -> str:
    """List a directory's immediate files/subdirectories and each file's top-level symbols."""
    result = _list_structure_impl(ListStructureInput(path=path), _get_repo_context())
    return result.model_dump_json()


@mcp.tool()
def ask_onboarding_question(question: str) -> str:
    """Ask a grounded, cited onboarding question about the ingested repo.

    Runs a full search -> read -> answer loop and returns JSON with `answer`, `citations`,
    `verified` (whether every citation was confirmed against code actually retrieved this
    session), and `unverified_citations`.
    """
    result = _ask_onboarding_question_impl(question, _get_repo_context())
    return result.model_dump_json()


def main() -> None:
    if not os.environ.get("ONBOARD_AGENT_REPO_URL"):
        print(
            "warning: ONBOARD_AGENT_REPO_URL is not set; tool calls will fail until it is.",
            file=sys.stderr,
        )
    mcp.run()


if __name__ == "__main__":
    main()
