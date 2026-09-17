"""Unit tests for URL validation and repo-map extraction — no network access needed."""

from pathlib import Path

import pytest

from onboard_agent.ingestion.clone import InvalidRepoUrlError, validate_github_url
from onboard_agent.ingestion.repo_map import build_repo_map

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "tiny_repo"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/psf/requests", ("psf", "requests")),
        ("https://github.com/psf/requests.git", ("psf", "requests")),
        ("https://github.com/psf/requests/", ("psf", "requests")),
    ],
)
def test_validate_github_url_accepts_https_github_urls(url, expected):
    assert validate_github_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:psf/requests.git",  # SSH — not accepted
        "http://github.com/psf/requests",  # not HTTPS
        "https://gitlab.com/psf/requests",  # not github.com
        "https://github.com/",  # no org/repo
        "not a url",
    ],
)
def test_validate_github_url_rejects_non_https_github_urls(url):
    with pytest.raises(InvalidRepoUrlError):
        validate_github_url(url)


def test_build_repo_map_extracts_directory_tree_and_skips_definitions():
    repo_map = build_repo_map(FIXTURE_REPO, "https://github.com/example/tiny_repo", "abc123")
    assert repo_map.repo_url == "https://github.com/example/tiny_repo"
    assert repo_map.commit_sha == "abc123"
    assert "plain_functions.py" in repo_map.directory_tree
    assert "canary.py" in repo_map.directory_tree
