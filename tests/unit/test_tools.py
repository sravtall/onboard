"""Unit tests for the shared tools/ core (search_codebase, read_file, list_structure) against
the synthetic fixture repo — including path-escape rejection."""

from pathlib import Path

import pytest

from onboard_agent.chunking.chunker import chunk_repo
from onboard_agent.indexing.hybrid import HybridRetriever
from onboard_agent.indexing.lexical import LexicalIndex
from onboard_agent.indexing.vector_store import VectorStore
from onboard_agent.ingestion.pipeline import RepoContext
from onboard_agent.ingestion.repo_map import build_repo_map
from onboard_agent.tools.list_structure import list_structure
from onboard_agent.tools.read_file import read_file
from onboard_agent.tools.schemas import (
    ListStructureInput,
    ReadFileInput,
    SearchCodebaseInput,
    ToolError,
)
from onboard_agent.tools.search_codebase import search_codebase

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "tiny_repo"


@pytest.fixture(scope="module")
def repo_context(tmp_path_factory) -> RepoContext:
    chunks = chunk_repo(FIXTURE_REPO)
    repo_map = build_repo_map(FIXTURE_REPO, "https://github.com/example/tiny_repo", "deadbeef")
    db_path = tmp_path_factory.mktemp("lancedb")
    retriever = HybridRetriever(VectorStore(db_path), LexicalIndex())
    retriever.build(chunks)
    return RepoContext(
        org="example",
        repo="tiny_repo",
        commit_sha="deadbeef",
        repo_root=FIXTURE_REPO,
        chunks=chunks,
        repo_map=repo_map,
        retriever=retriever,
    )


def test_search_codebase_returns_citations(repo_context):
    output = search_codebase(SearchCodebaseInput(query="add_user", top_k=3), repo_context)
    assert output.results
    assert output.results[0].citation.startswith("classes_and_methods.py:")


def test_read_file_returns_requested_line_range(repo_context):
    output = read_file(
        ReadFileInput(path="plain_functions.py", start_line=6, end_line=8), repo_context
    )
    assert output.start_line == 6
    assert output.end_line == 8
    assert "def add" in output.content


def test_read_file_defaults_to_whole_file(repo_context):
    output = read_file(ReadFileInput(path="constants_only.py"), repo_context)
    assert "MAX_RETRIES" in output.content


def test_read_file_rejects_path_escaping_the_repo_root(repo_context):
    result = read_file(ReadFileInput(path="../../etc/passwd"), repo_context)
    assert isinstance(result, ToolError)


def test_read_file_rejects_absolute_path(repo_context):
    result = read_file(ReadFileInput(path="/etc/passwd"), repo_context)
    assert isinstance(result, ToolError)


def test_read_file_reports_missing_file(repo_context):
    result = read_file(ReadFileInput(path="does_not_exist.py"), repo_context)
    assert isinstance(result, ToolError)


def test_list_structure_lists_files_with_their_symbols(repo_context):
    output = list_structure(ListStructureInput(path="."), repo_context)
    by_path = {e.path: e for e in output.entries}
    assert "plain_functions.py" in by_path
    assert "add" in by_path["plain_functions.py"].symbols
    assert "subtract" in by_path["plain_functions.py"].symbols


def test_list_structure_rejects_path_escaping_the_repo_root(repo_context):
    result = list_structure(ListStructureInput(path="../.."), repo_context)
    assert isinstance(result, ToolError)


def test_list_structure_rejects_a_file_path(repo_context):
    result = list_structure(ListStructureInput(path="plain_functions.py"), repo_context)
    assert isinstance(result, ToolError)
