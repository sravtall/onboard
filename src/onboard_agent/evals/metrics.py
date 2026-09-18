"""Eval report data model and Markdown rendering for docs/EVALS.md."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RepoEvalResult:
    repo_label: str
    retrieval_recall: float
    citation_groundedness: float | None
    refusal_accuracy: float | None
    num_answerable: int
    num_unanswerable: int


@dataclass
class EvalReport:
    rows: list[RepoEvalResult]

    def write_markdown(self, path: Path) -> None:
        lines = [
            "# OnboardAgent Evals",
            "",
            "Metrics: **Retrieval Recall@K** (did the right file come back for an answerable "
            "question with a known-relevant file?), **Citation Groundedness** (fraction of "
            "citations in answerable-question answers that are confirmed against code actually "
            "retrieved that session), **Refusal Accuracy** (fraction of deliberately "
            "unanswerable questions answered without a fabricated citation).",
            "",
            "| Repo | Questions (answerable / unanswerable) | Retrieval Recall@K | "
            "Citation Groundedness | Refusal Accuracy |",
            "|---|---|---|---|---|",
        ]
        for row in self.rows:
            cg = "n/a" if row.citation_groundedness is None else f"{row.citation_groundedness:.0%}"
            ra = "n/a" if row.refusal_accuracy is None else f"{row.refusal_accuracy:.0%}"
            lines.append(
                f"| {row.repo_label} | {row.num_answerable} / {row.num_unanswerable} | "
                f"{row.retrieval_recall:.0%} | {cg} | {ra} |"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
