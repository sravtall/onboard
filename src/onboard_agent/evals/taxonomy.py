"""Failure taxonomy for eval results: classifies each answered question into a labeled failure
mode (or `correct`) so `docs/EVALS.md` can show *how* things fail, not just aggregate rates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FailureLabel(StrEnum):
    CORRECT = "correct"
    RETRIEVAL_MISS = "retrieval_miss"
    WRONG_LINES = "wrong_lines"
    HALLUCINATED = "hallucinated"
    SHOULD_REFUSE_BUT_DIDNT = "should_refuse_but_didnt"
    INCORRECTLY_REFUSED = "incorrectly_refused"
    NEEDS_REVIEW = "needs_review"


@dataclass
class QuestionResult:
    """The full record of scoring one eval question against a live answer."""

    question_id: str
    question: str
    answerable: bool
    expected_relevant_files: list[str]
    retrieved_files: list[str]
    citations: list[str]
    verified: bool
    unverified_citations: list[str]
    failure_label: FailureLabel


def summarize_taxonomy(results: list[QuestionResult]) -> dict[FailureLabel, int]:
    """Count occurrences of each failure label, including zero-count labels so the taxonomy
    table always shows the full label set."""
    counts: dict[FailureLabel, int] = {label: 0 for label in FailureLabel}
    for result in results:
        counts[result.failure_label] += 1
    return counts


def citation_groundedness_from_results(results: list[QuestionResult]) -> float | None:
    """Same definition as evals.harness.score_answering's first return value, derived from
    already-computed QuestionResults instead of making a second round of live calls."""
    answerable = [r for r in results if r.answerable]
    total = sum(len(r.citations) for r in answerable)
    grounded = sum(len(r.citations) - len(r.unverified_citations) for r in answerable)
    return (grounded / total) if total else None


def refusal_accuracy_from_results(results: list[QuestionResult]) -> float | None:
    """Same definition as evals.harness.score_answering's second return value, derived from
    already-computed QuestionResults instead of making a second round of live calls."""
    unanswerable = [r for r in results if not r.answerable]
    if not unanswerable:
        return None
    correct = sum(1 for r in unanswerable if r.verified)
    return correct / len(unanswerable)
