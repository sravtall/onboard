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


def test_bare_filename_citation_resolves_to_unique_retrieved_path(tmp_path):
    """Observed live: the model sometimes cites a bare filename (`module.py:1-2`) instead of the
    full relative path it was actually retrieved under (`sub/module.py:1-2`) -- this should still
    verify, and the stored citation should show the real, resolvable path, not the bare one."""
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "module.py").write_text("def f():\n    pass\n", encoding="utf-8")
    retrieved = [RetrievedSpan("sub/module.py", 1, 2)]

    report = verify_answer("See module.py:1-2.", tmp_path, retrieved)

    assert report.verified
    assert report.citations[0].file_path == "sub/module.py"


def test_ambiguous_bare_filename_citation_is_not_resolved(tmp_path):
    """Two retrieved files sharing a basename (e.g. two __init__.py's) must not be silently
    matched to the wrong one -- an ambiguous abbreviation correctly fails verification."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "module.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "b" / "module.py").write_text("y = 2\n", encoding="utf-8")
    retrieved = [RetrievedSpan("a/module.py", 1, 1), RetrievedSpan("b/module.py", 1, 1)]

    report = verify_answer("See module.py:1-1.", tmp_path, retrieved)

    assert not report.verified


def test_full_path_citation_is_unaffected_by_canonicalization(tmp_path):
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "module.py").write_text("def f():\n    pass\n", encoding="utf-8")
    retrieved = [RetrievedSpan("sub/module.py", 1, 2)]

    report = verify_answer("See sub/module.py:1-2.", tmp_path, retrieved)

    assert report.verified
    assert report.citations[0].file_path == "sub/module.py"
