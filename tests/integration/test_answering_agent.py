"""Phase 3 exit criteria: end-to-end question -> retrieval -> cited, grounded answer; honest
refusal (no fabricated citation) when the codebase genuinely doesn't contain the answer.

Calls the real Anthropic API — requires ANTHROPIC_API_KEY (auto-skipped otherwise, see
tests/conftest.py)."""

from pathlib import Path

import pytest

from onboard_agent.agent.loop import ask_onboarding_question
from onboard_agent.chunking.chunker import chunk_repo
from onboard_agent.indexing.hybrid import HybridRetriever
from onboard_agent.indexing.lexical import LexicalIndex
from onboard_agent.indexing.vector_store import VectorStore
from onboard_agent.ingestion.pipeline import RepoContext
from onboard_agent.ingestion.repo_map import build_repo_map

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "tiny_repo"

pytestmark = pytest.mark.requires_api_key


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


def test_answerable_question_gets_a_grounded_cited_answer(repo_context):
    result = ask_onboarding_question("How do I register a new user?", repo_context)

    assert result.answer.strip()
    assert result.citations, "expected at least one citation for an answerable question"
    assert result.verified, f"unverified citations: {result.unverified_citations}"
    assert any("classes_and_methods.py" in c for c in result.citations)


def test_unanswerable_question_does_not_fabricate_a_citation(repo_context):
    result = ask_onboarding_question(
        "How does this codebase integrate with Stripe for payment processing?", repo_context
    )

    assert result.verified, f"unverified citations: {result.unverified_citations}"
    # Either it cited nothing (clean refusal) or every citation it did make is real and
    # actually-retrieved (verified above) — but it must not claim Stripe integration exists.
    assert "stripe" not in result.answer.lower() or any(
        phrase in result.answer.lower()
        for phrase in (
            "couldn't find",
            "cannot find",
            "no stripe",
            "does not",
            "doesn't",
            "not found",
            "no evidence",
        )
    )
