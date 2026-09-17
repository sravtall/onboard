"""Unit tests for the eval harness's scoring logic against the fast synthetic fixture repo —
no network access, and citation-groundedness/refusal-accuracy scoring (which calls the real
answering agent) is exercised separately as a live test."""

from pathlib import Path

import pytest

from onboard_agent.chunking.chunker import chunk_repo
from onboard_agent.evals.harness import EvalQuestion, load_fixture, score_retrieval_recall
from onboard_agent.evals.metrics import EvalReport, RepoEvalResult
from onboard_agent.indexing.hybrid import HybridRetriever
from onboard_agent.indexing.lexical import LexicalIndex
from onboard_agent.indexing.vector_store import VectorStore
from onboard_agent.ingestion.pipeline import RepoContext
from onboard_agent.ingestion.repo_map import build_repo_map

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "tiny_repo"
SAMPLE_FIXTURE_YAML = Path(__file__).parent.parent / "fixtures" / "eval_tiny_repo.yaml"


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


def test_load_fixture_parses_questions():
    repo_url, questions = load_fixture(SAMPLE_FIXTURE_YAML)
    assert repo_url == "https://github.com/example/tiny_repo"
    assert any(q.question == "How do I register a new user?" for q in questions)
    assert any(not q.answerable for q in questions)


def test_score_retrieval_recall_finds_the_expected_file(repo_context):
    questions = [
        EvalQuestion(
            question="How do I register a new user?",
            answerable=True,
            expected_relevant_files=["classes_and_methods.py"],
        )
    ]
    recall = score_retrieval_recall(repo_context, questions)
    assert recall == 1.0


def test_score_retrieval_recall_zero_when_expected_file_is_wrong(repo_context):
    questions = [
        EvalQuestion(
            question="How do I register a new user?",
            answerable=True,
            expected_relevant_files=["nonexistent_file.py"],
        )
    ]
    recall = score_retrieval_recall(repo_context, questions)
    assert recall == 0.0


def test_score_retrieval_recall_ignores_unanswerable_and_unlabeled_questions(repo_context):
    questions = [
        EvalQuestion(question="Something unanswerable", answerable=False),
        EvalQuestion(question="No expected files given", answerable=True),
    ]
    # No questions with expected_relevant_files -> vacuously perfect recall
    assert score_retrieval_recall(repo_context, questions) == 1.0


def test_eval_report_writes_markdown_table(tmp_path):
    report = EvalReport(
        rows=[
            RepoEvalResult(
                repo_label="example/tiny_repo",
                retrieval_recall=1.0,
                citation_groundedness=0.9,
                refusal_accuracy=1.0,
                num_answerable=5,
                num_unanswerable=2,
            )
        ]
    )
    out_path = tmp_path / "EVALS.md"
    report.write_markdown(out_path)
    content = out_path.read_text(encoding="utf-8")
    assert "example/tiny_repo" in content
    assert "100%" in content
    assert "90%" in content
