"""Eval harness: for each fixture repo, score retrieval recall, and — unless --retrieval-only —
citation groundedness and refusal accuracy from the answering agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from onboard_agent.agent.loop import AnswerResult, ask_onboarding_question
from onboard_agent.evals.metrics import EvalReport, RepoEvalResult
from onboard_agent.evals.taxonomy import FailureLabel, QuestionResult
from onboard_agent.ingestion.pipeline import RepoContext, get_or_ingest_repo_context
from onboard_agent.tools.schemas import SearchCodebaseInput
from onboard_agent.tools.search_codebase import search_codebase

DEFAULT_FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEFAULT_TOP_K = 8


@dataclass
class EvalQuestion:
    question: str
    answerable: bool = True
    expected_relevant_files: list[str] = field(default_factory=list)
    question_id: str = ""
    notes: str = ""


def load_fixture(path: Path) -> tuple[str, list[EvalQuestion]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = [
        EvalQuestion(
            question=q["question"],
            answerable=q.get("answerable", True),
            expected_relevant_files=q.get("expected_relevant_files", []),
            question_id=q.get("question_id", ""),
            notes=q.get("notes", ""),
        )
        for q in data["questions"]
    ]
    return data["repo_url"], questions


def score_retrieval_recall(
    ctx: RepoContext, questions: list[EvalQuestion], top_k: int = DEFAULT_TOP_K
) -> float:
    """Fraction of answerable questions (with a known expected file) for which that file
    appears somewhere in the top-K search_codebase results."""
    scored = [q for q in questions if q.answerable and q.expected_relevant_files]
    if not scored:
        return 1.0

    hits = 0
    for q in scored:
        result = search_codebase(SearchCodebaseInput(query=q.question, top_k=top_k), ctx)
        retrieved_files = {r.file_path for r in result.results}
        if retrieved_files & set(q.expected_relevant_files):
            hits += 1
    return hits / len(scored)


def score_answering(
    ctx: RepoContext, questions: list[EvalQuestion]
) -> tuple[float | None, float | None]:
    """Citation groundedness over answerable questions, and refusal accuracy over
    deliberately-unanswerable ones. Both call the real answering agent."""
    answerable = [q for q in questions if q.answerable]
    unanswerable = [q for q in questions if not q.answerable]

    total_citations = 0
    grounded_citations = 0
    for q in answerable:
        result = ask_onboarding_question(q.question, ctx)
        total_citations += len(result.citations)
        grounded_citations += len(result.citations) - len(result.unverified_citations)
    citation_groundedness = (grounded_citations / total_citations) if total_citations else None

    correct_refusals = 0
    for q in unanswerable:
        result = ask_onboarding_question(q.question, ctx)
        # A correct refusal never fabricates a citation, regardless of exact wording.
        if result.verified:
            correct_refusals += 1
    refusal_accuracy = (correct_refusals / len(unanswerable)) if unanswerable else None

    return citation_groundedness, refusal_accuracy


def classify_question_result(
    ctx: RepoContext,
    question: EvalQuestion,
    result: AnswerResult,
    top_k: int = DEFAULT_TOP_K,
) -> QuestionResult:
    """Label one already-answered question with a FailureLabel. `wrong_lines` is intentionally
    never assigned automatically (see docs/PLAN.md) — a file-level hit with no ground-truth line
    range to check against is scored `correct`; a case where the expected file was retrievable
    but never cited comes back `needs_review` for a manual/explore-assisted follow-up pass."""
    search_result = search_codebase(SearchCodebaseInput(query=question.question, top_k=top_k), ctx)
    retrieved_files = [r.file_path for r in search_result.results]

    if question.answerable:
        if not result.verified:
            label = FailureLabel.HALLUCINATED
        elif not result.citations:
            label = FailureLabel.INCORRECTLY_REFUSED
        elif question.expected_relevant_files:
            cited_files = {c.split(":", 1)[0] for c in result.citations}
            expected = set(question.expected_relevant_files)
            if cited_files & expected:
                label = FailureLabel.CORRECT
            elif set(retrieved_files) & expected:
                label = FailureLabel.NEEDS_REVIEW
            else:
                label = FailureLabel.RETRIEVAL_MISS
        else:
            label = FailureLabel.CORRECT
    else:
        label = FailureLabel.CORRECT if result.verified else FailureLabel.SHOULD_REFUSE_BUT_DIDNT

    return QuestionResult(
        question_id=question.question_id or question.question[:48],
        question=question.question,
        answerable=question.answerable,
        expected_relevant_files=question.expected_relevant_files,
        retrieved_files=retrieved_files,
        citations=result.citations,
        verified=result.verified,
        unverified_citations=result.unverified_citations,
        failure_label=label,
    )


def run_taxonomy_eval(ctx: RepoContext, questions: list[EvalQuestion]) -> list[QuestionResult]:
    """Run the live answering agent once per question and classify each result — the detailed,
    per-question counterpart to score_answering's two aggregate rates. Use
    taxonomy.citation_groundedness_from_results / taxonomy.refusal_accuracy_from_results to
    derive the same two aggregates from the returned list without a second round of live calls."""
    return [
        classify_question_result(ctx, q, ask_onboarding_question(q.question, ctx))
        for q in questions
    ]


def run_evals(fixtures_dir: Path | None = None, retrieval_only: bool = False) -> EvalReport:
    fixtures_dir = fixtures_dir or DEFAULT_FIXTURES_DIR
    rows: list[RepoEvalResult] = []

    for fixture_path in sorted(fixtures_dir.glob("*.yaml")):
        repo_url, questions = load_fixture(fixture_path)
        ctx = get_or_ingest_repo_context(repo_url)

        retrieval_recall = score_retrieval_recall(ctx, questions)
        citation_groundedness: float | None = None
        refusal_accuracy: float | None = None
        if not retrieval_only:
            citation_groundedness, refusal_accuracy = score_answering(ctx, questions)

        rows.append(
            RepoEvalResult(
                repo_label=f"{ctx.org}/{ctx.repo}",
                retrieval_recall=retrieval_recall,
                citation_groundedness=citation_groundedness,
                refusal_accuracy=refusal_accuracy,
                num_answerable=sum(1 for q in questions if q.answerable),
                num_unanswerable=sum(1 for q in questions if not q.answerable),
            )
        )

    return EvalReport(rows=rows)
