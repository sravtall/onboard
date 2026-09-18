"""Unit tests for failure-taxonomy classification logic — synthetic AnswerResults, no live API
calls. Retrieval (search_codebase) still runs for real against the tiny fixture repo."""

from pathlib import Path

import pytest

from onboard_agent.agent.loop import AnswerResult
from onboard_agent.chunking.chunker import chunk_repo
from onboard_agent.evals.harness import EvalQuestion, classify_question_result
from onboard_agent.evals.taxonomy import (
    FailureLabel,
    QuestionResult,
    citation_groundedness_from_results,
    refusal_accuracy_from_results,
    summarize_taxonomy,
)
from onboard_agent.indexing.hybrid import HybridRetriever
from onboard_agent.indexing.lexical import LexicalIndex
from onboard_agent.indexing.vector_store import VectorStore
from onboard_agent.ingestion.pipeline import RepoContext
from onboard_agent.ingestion.repo_map import build_repo_map

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


def _answer(citations, verified, unverified=None) -> AnswerResult:
    return AnswerResult(
        question="q",
        answer="a",
        citations=citations,
        verified=verified,
        unverified_citations=unverified or [],
    )


def test_correct_when_expected_file_is_cited_and_grounded(repo_context):
    question = EvalQuestion(
        question="add_user", answerable=True, expected_relevant_files=["classes_and_methods.py"]
    )
    answer = _answer(["classes_and_methods.py:8-10"], verified=True)
    result = classify_question_result(repo_context, question, answer)
    assert result.failure_label == FailureLabel.CORRECT


def test_hallucinated_when_not_verified(repo_context):
    question = EvalQuestion(
        question="add_user", answerable=True, expected_relevant_files=["classes_and_methods.py"]
    )
    answer = _answer(
        ["classes_and_methods.py:999-1000"],
        verified=False,
        unverified=["classes_and_methods.py:999-1000"],
    )
    result = classify_question_result(repo_context, question, answer)
    assert result.failure_label == FailureLabel.HALLUCINATED


def test_incorrectly_refused_when_answerable_but_no_citations(repo_context):
    question = EvalQuestion(
        question="add_user", answerable=True, expected_relevant_files=["classes_and_methods.py"]
    )
    answer = _answer([], verified=True)
    result = classify_question_result(repo_context, question, answer)
    assert result.failure_label == FailureLabel.INCORRECTLY_REFUSED


def test_retrieval_miss_when_expected_file_never_surfaces(repo_context):
    question = EvalQuestion(
        question="add_user", answerable=True, expected_relevant_files=["nonexistent_file.py"]
    )
    answer = _answer(["classes_and_methods.py:8-10"], verified=True)
    result = classify_question_result(repo_context, question, answer)
    assert result.failure_label == FailureLabel.RETRIEVAL_MISS


def test_correct_when_unanswerable_question_is_verified_refusal(repo_context):
    question = EvalQuestion(question="does this integrate with stripe", answerable=False)
    answer = _answer([], verified=True)
    result = classify_question_result(repo_context, question, answer)
    assert result.failure_label == FailureLabel.CORRECT


def test_should_refuse_but_didnt_when_unanswerable_question_not_verified(repo_context):
    question = EvalQuestion(question="does this integrate with stripe", answerable=False)
    answer = _answer(
        ["classes_and_methods.py:8-10"], verified=False, unverified=["classes_and_methods.py:8-10"]
    )
    result = classify_question_result(repo_context, question, answer)
    assert result.failure_label == FailureLabel.SHOULD_REFUSE_BUT_DIDNT


def test_summarize_taxonomy_counts_every_label_including_zero():
    results = [
        QuestionResult("q1", "q1", True, [], [], [], True, [], FailureLabel.CORRECT),
        QuestionResult("q2", "q2", True, [], [], [], True, [], FailureLabel.CORRECT),
        QuestionResult(
            "q3", "q3", False, [], [], [], False, [], FailureLabel.SHOULD_REFUSE_BUT_DIDNT
        ),
    ]
    counts = summarize_taxonomy(results)
    assert counts[FailureLabel.CORRECT] == 2
    assert counts[FailureLabel.SHOULD_REFUSE_BUT_DIDNT] == 1
    assert counts[FailureLabel.HALLUCINATED] == 0  # zero-count labels are still present


def test_citation_groundedness_and_refusal_accuracy_from_results():
    results = [
        QuestionResult("q1", "q1", True, [], [], ["a.py:1-2"], True, [], FailureLabel.CORRECT),
        QuestionResult(
            "q2",
            "q2",
            True,
            [],
            [],
            ["b.py:1-2", "b.py:3-4"],
            False,
            ["b.py:3-4"],
            FailureLabel.HALLUCINATED,
        ),
        QuestionResult("q3", "q3", False, [], [], [], True, [], FailureLabel.CORRECT),
        QuestionResult(
            "q4", "q4", False, [], [], [], False, [], FailureLabel.SHOULD_REFUSE_BUT_DIDNT
        ),
    ]
    # answerable: 3 total citations, 2 grounded (a.py + b.py:1-2) -> 2/3
    assert citation_groundedness_from_results(results) == pytest.approx(2 / 3)
    # unanswerable: 1 of 2 verified -> 0.5
    assert refusal_accuracy_from_results(results) == 0.5


def test_citation_groundedness_is_none_with_no_citations():
    results = [QuestionResult("q1", "q1", True, [], [], [], True, [], FailureLabel.CORRECT)]
    assert citation_groundedness_from_results(results) is None


def test_refusal_accuracy_is_none_with_no_unanswerable_questions():
    results = [
        QuestionResult("q1", "q1", True, [], [], ["a.py:1-2"], True, [], FailureLabel.CORRECT)
    ]
    assert refusal_accuracy_from_results(results) is None
