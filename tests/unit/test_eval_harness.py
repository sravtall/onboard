"""Unit tests for the eval harness's scoring logic against the fast synthetic fixture repo —
no network access, and citation-groundedness/refusal-accuracy scoring (which calls the real
answering agent) is exercised separately as a live test."""

from pathlib import Path

import pytest

from onboard_agent.chunking.chunker import chunk_repo
from onboard_agent.evals.harness import (
    EvalQuestion,
    load_fixture,
    load_overview_check,
    score_overview_accuracy,
    score_retrieval_recall,
)
from onboard_agent.evals.metrics import EvalReport, RepoEvalResult
from onboard_agent.indexing.hybrid import HybridRetriever
from onboard_agent.indexing.lexical import LexicalIndex
from onboard_agent.indexing.vector_store import VectorStore
from onboard_agent.ingestion.pipeline import RepoContext
from onboard_agent.ingestion.repo_map import build_repo_map
from onboard_agent.tools.schemas import GenerateOverviewOutput, OverviewSection

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


def _overview(entry_points, key_modules_text) -> GenerateOverviewOutput:
    return GenerateOverviewOutput(
        architecture_summary="",
        key_modules=[OverviewSection(heading="mod", content=key_modules_text)],
        directory_map="",
        entry_points=entry_points,
        how_to_run_and_test="",
        where_to_start="",
        citations=[],
        verified=True,
        unverified_citations=[],
    )


def test_score_overview_accuracy_full_match():
    result = _overview(["cli.py entry point"], "see app.py and sessions.py for the core logic")
    entry_recall, module_recall = score_overview_accuracy(
        result, expected_entry_points=["cli.py"], expected_key_modules=["app.py", "sessions.py"]
    )
    assert entry_recall == 1.0
    assert module_recall == 1.0


def test_score_overview_accuracy_partial_match_is_case_insensitive():
    result = _overview(["CLI.PY"], "only App.py is mentioned here")
    entry_recall, module_recall = score_overview_accuracy(
        result, expected_entry_points=["cli.py"], expected_key_modules=["app.py", "sessions.py"]
    )
    assert entry_recall == 1.0
    assert module_recall == 0.5


def test_score_overview_accuracy_vacuously_perfect_when_nothing_expected():
    result = _overview([], "")
    entry_recall, module_recall = score_overview_accuracy(
        result, expected_entry_points=[], expected_key_modules=[]
    )
    assert entry_recall == 1.0
    assert module_recall == 1.0


def test_load_overview_check_reads_the_block(tmp_path):
    fixture = tmp_path / "fixture.yaml"
    fixture.write_text(
        "repo_url: https://example.com/repo\n"
        "questions: []\n"
        "overview_check:\n"
        "  expected_entry_points: [cli.py]\n"
        "  expected_key_modules: [app.py, sessions.py]\n",
        encoding="utf-8",
    )
    check = load_overview_check(fixture)
    assert check == (["cli.py"], ["app.py", "sessions.py"])


def test_load_overview_check_returns_none_when_absent(tmp_path):
    fixture = tmp_path / "fixture.yaml"
    fixture.write_text("repo_url: https://example.com/repo\nquestions: []\n", encoding="utf-8")
    assert load_overview_check(fixture) is None


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
