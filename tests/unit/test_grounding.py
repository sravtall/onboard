"""Unit tests for citation extraction and grounding verification — no API calls."""

from pathlib import Path

from onboard_agent.agent.grounding import RetrievedSpan, extract_citations, verify_answer

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "tiny_repo"


def test_extract_citations_finds_all_and_deduplicates():
    text = (
        "See plain_functions.py:6-8 and classes_and_methods.py:8-10. "
        "Also plain_functions.py:6-8 again."
    )
    citations = extract_citations(text)
    assert len(citations) == 2
    assert {c.as_str() for c in citations} == {
        "plain_functions.py:6-8",
        "classes_and_methods.py:8-10",
    }


def test_citation_matching_a_single_retrieved_span_is_verified():
    retrieved = [RetrievedSpan("plain_functions.py", 6, 8)]
    report = verify_answer("See plain_functions.py:6-8.", FIXTURE_REPO, retrieved)
    assert report.verified


def test_citation_merging_two_adjacent_retrieved_spans_is_verified():
    """The model may summarize two nearby retrieved chunks (e.g. two functions separated by a
    couple of blank lines) as one combined citation — this should count as grounded, not
    penalized, since every line in the range was actually surfaced."""
    retrieved = [
        RetrievedSpan("plain_functions.py", 6, 8),  # add()
        RetrievedSpan("plain_functions.py", 11, 12),  # subtract(), 2-line gap from add()
    ]
    report = verify_answer("See plain_functions.py:6-12.", FIXTURE_REPO, retrieved)
    assert report.verified


def test_citation_spanning_a_large_unretrieved_gap_is_not_verified():
    retrieved = [
        RetrievedSpan("plain_functions.py", 1, 2),
        RetrievedSpan("plain_functions.py", 12, 12),
    ]
    report = verify_answer("See plain_functions.py:1-12.", FIXTURE_REPO, retrieved)
    assert not report.verified


def test_citation_to_a_file_never_retrieved_is_not_verified():
    report = verify_answer("See canary.py:1-5.", FIXTURE_REPO, retrieved=[])
    assert not report.verified
    assert report.unverified_citations == [report.citations[0]]


def test_citation_to_a_real_file_but_out_of_bounds_line_range_is_not_verified():
    retrieved = [RetrievedSpan("constants_only.py", 1, 999)]
    report = verify_answer("See constants_only.py:1-999.", FIXTURE_REPO, retrieved)
    assert not report.verified  # constants_only.py doesn't have 999 lines


def test_answer_with_no_citations_is_trivially_verified():
    report = verify_answer("I couldn't find anything about this in the repo.", FIXTURE_REPO, [])
    assert report.verified
    assert report.citations == []
