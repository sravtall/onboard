"""Citation grounding: extract `file:start-end` citations from an answer and verify each one
(a) resolves to a real, in-bounds location in the repo, and (b) was actually surfaced by a tool
call during this session — the stronger signal, since (a) alone would pass a citation the model
invented but which happens to be valid."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from onboard_agent.tools.path_safety import PathEscapesRepoError, resolve_within_repo

_CITATION_RE = re.compile(r"([\w./\\-]+\.py):(\d+)-(\d+)")


@dataclass(frozen=True)
class Citation:
    file_path: str
    start_line: int
    end_line: int

    def as_str(self) -> str:
        return f"{self.file_path}:{self.start_line}-{self.end_line}"


@dataclass(frozen=True)
class RetrievedSpan:
    file_path: str
    start_line: int
    end_line: int


@dataclass
class GroundingReport:
    citations: list[Citation]
    unverified_citations: list[Citation]

    @property
    def verified(self) -> bool:
        return not self.unverified_citations


def extract_citations(text: str) -> list[Citation]:
    seen: dict[tuple[str, int, int], Citation] = {}
    for match in _CITATION_RE.finditer(text):
        file_path, start, end = match.group(1), int(match.group(2)), int(match.group(3))
        seen[(file_path, start, end)] = Citation(file_path, start, end)
    return list(seen.values())


def _exists_on_disk(citation: Citation, repo_root: Path) -> bool:
    try:
        target = resolve_within_repo(repo_root, citation.file_path)
    except PathEscapesRepoError:
        return False
    if not target.is_file():
        return False
    try:
        line_count = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return False
    return 1 <= citation.start_line <= citation.end_line <= line_count


_MERGE_GAP_TOLERANCE = 3


def _merge_spans(
    spans: list[RetrievedSpan], gap_tolerance: int = _MERGE_GAP_TOLERANCE
) -> list[tuple[int, int]]:
    """Merge retrieved spans (already filtered to one file) that are adjacent or close
    together, so a citation that spans two retrieved chunks it read back-to-back — e.g. two
    functions separated by a couple of blank lines — is recognized as grounded rather than
    penalized for the model's summarizing them as one combined range."""
    ranges = sorted((s.start_line, s.end_line) for s in spans)
    merged: list[tuple[int, int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1] + gap_tolerance + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _was_retrieved(citation: Citation, retrieved: list[RetrievedSpan]) -> bool:
    same_file = [s for s in retrieved if s.file_path == citation.file_path]
    if not same_file:
        return False
    return any(
        start <= citation.start_line and citation.end_line <= end
        for start, end in _merge_spans(same_file)
    )


def verify_answer(
    answer_text: str, repo_root: Path, retrieved: list[RetrievedSpan]
) -> GroundingReport:
    citations = extract_citations(answer_text)
    unverified = [
        c for c in citations if not (_exists_on_disk(c, repo_root) and _was_retrieved(c, retrieved))
    ]
    return GroundingReport(citations=citations, unverified_citations=unverified)
