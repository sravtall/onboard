"""Sandboxed cloning of untrusted repos. The cloned tree is analyzed (parsed, read) — never
executed. Nothing here `import`s, `exec`s, or subprocess-runs anything from inside the clone."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

_GITHUB_HTTPS_RE = re.compile(
    r"^https://github\.com/(?P<org>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$"
)


class InvalidRepoUrlError(ValueError):
    pass


class CloneError(RuntimeError):
    pass


def validate_github_url(url: str) -> tuple[str, str]:
    """Validate that `url` is an HTTPS github.com repo URL. Returns (org, repo).

    HTTPS-only and github.com-only by design: this tool clones arbitrary public repos on the
    user's behalf, so it must not accept `git@`/SSH URLs (which could be scoped to private
    repos via the invoking user's own credentials) or arbitrary hosts.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise InvalidRepoUrlError(f"Only https://github.com/<org>/<repo> URLs are supported: {url}")
    match = _GITHUB_HTTPS_RE.match(url)
    if not match:
        raise InvalidRepoUrlError(f"Could not parse a GitHub org/repo from: {url}")
    return match.group("org"), match.group("repo")


@contextmanager
def clone_repo_to_sandbox(url: str):
    """Clone `url` into an isolated temp directory and yield its Path. The directory (and
    everything in it) is deleted on exit, whether or not the block succeeds.

    Uses a shallow clone (--depth 1) purely as a read-only source tree. Never executes anything
    inside the cloned directory.
    """
    validate_github_url(url)
    sandbox_dir = Path(tempfile.mkdtemp(prefix="onboard-agent-clone-"))
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", url, str(sandbox_dir)],
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if result.returncode != 0:
            raise CloneError(f"git clone failed for {url}: {result.stderr.strip()}")
        yield sandbox_dir
    finally:
        shutil.rmtree(sandbox_dir, ignore_errors=True)


def get_commit_sha(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"
