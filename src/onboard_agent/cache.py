"""Per-repo cache layout, keyed by org/repo/commit so re-ingesting an unchanged repo is a
cache hit. The persisted clone under `clone/` is a read-only copy of untrusted third-party
code — every reader (chunker, read_file, list_structure) may parse or read it, but nothing in
this codebase may import, exec, or subprocess-run anything from inside it.
"""

from __future__ import annotations

import os
from pathlib import Path


def cache_root() -> Path:
    override = os.environ.get("ONBOARD_AGENT_CACHE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".onboard_agent_cache"


def repo_cache_dir(org: str, repo: str, commit_sha: str) -> Path:
    short_sha = commit_sha[:12]
    directory = cache_root() / "repos" / f"{org}__{repo}__{short_sha}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def cloned_repo_path(repo_dir: Path) -> Path:
    return repo_dir / "clone"


def chunks_path(repo_dir: Path) -> Path:
    return repo_dir / "chunks.jsonl"


def repo_map_path(repo_dir: Path) -> Path:
    return repo_dir / "repo_map.json"


def lancedb_path(repo_dir: Path) -> Path:
    return repo_dir / "lancedb"
