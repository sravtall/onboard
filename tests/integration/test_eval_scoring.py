"""Live check that score_answering's groundedness/refusal-accuracy math lines up with real
agent output (kept to 2 questions total to bound API cost)."""

from pathlib import Path

import pytest

from onboard_agent.chunking.chunker import chunk_repo
from onboard_agent.evals.harness import EvalQuestion, score_answering
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


def test_score_answering_reports_full_groundedness_and_refusal_accuracy(repo_context):
    questions = [
        EvalQuestion(question="How do I register a new user?", answerable=True),
        EvalQuestion(
            question="How does this repo integrate with Stripe for payment processing?",
            answerable=False,
        ),
    ]
    citation_groundedness, refusal_accuracy = score_answering(repo_context, questions)

    assert citation_groundedness is not None
    assert citation_groundedness == 1.0
    assert refusal_accuracy == 1.0
