"""Orchestrates ingestion end to end: clone -> chunk -> repo-map -> hybrid index -> persist.

The network clone happens in a sandboxed temp dir (ingestion/clone.py) and is deleted the
moment its read-only copy has been written into the persistent per-repo cache — the persisted
copy is what every later `read_file`/`list_structure` call and re-run of `onboard ask` reads
from. Nothing in this pipeline ever imports, execs, or subprocess-runs the cloned repo's code.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from onboard_agent.cache import (
    chunks_path,
    cloned_repo_path,
    lancedb_path,
    repo_cache_dir,
    repo_map_path,
)
from onboard_agent.chunking.chunker import chunk_repo
from onboard_agent.chunking.models import Chunk, RepoMap
from onboard_agent.indexing.hybrid import HybridRetriever
from onboard_agent.indexing.lexical import LexicalIndex
from onboard_agent.indexing.vector_store import VectorStore
from onboard_agent.ingestion.clone import clone_repo_to_sandbox, get_commit_sha, validate_github_url
from onboard_agent.ingestion.repo_map import build_repo_map


@dataclass
class RepoContext:
    """Everything a retrieval tool or the answering agent needs about one ingested repo."""

    org: str
    repo: str
    commit_sha: str
    repo_root: Path  # persistent, read-only copy of the cloned repo
    chunks: list[Chunk]
    repo_map: RepoMap
    retriever: HybridRetriever

    def chunk_by_id(self, chunk_id: str) -> Chunk | None:
        return next((c for c in self.chunks if c.chunk_id == chunk_id), None)


def _write_chunks(chunks: list[Chunk], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk.model_dump_json())
            f.write("\n")


def _read_chunks(path: Path) -> list[Chunk]:
    chunks = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(Chunk.model_validate_json(line))
    return chunks


def _build_context_from_directory(
    source_dir: Path, org: str, repo: str, repo_url: str, commit_sha: str, cache_dir: Path
) -> RepoContext:
    """Chunk, map, index, and persist a repo whose files already sit in `source_dir` (already a
    persistent, read-only location — this never touches the network or the original clone)."""
    chunks = chunk_repo(source_dir)
    repo_map = build_repo_map(source_dir, repo_url, commit_sha)

    _write_chunks(chunks, chunks_path(cache_dir))
    repo_map_path(cache_dir).write_text(repo_map.model_dump_json(indent=2), encoding="utf-8")

    retriever = HybridRetriever(VectorStore(lancedb_path(cache_dir)), LexicalIndex())
    retriever.build(chunks)

    return RepoContext(
        org=org,
        repo=repo,
        commit_sha=commit_sha,
        repo_root=source_dir,
        chunks=chunks,
        repo_map=repo_map,
        retriever=retriever,
    )


def ingest_repo(url: str) -> RepoContext:
    """Clone `url`, chunk it, build the repo map and hybrid index, and persist everything to
    the per-repo cache. Always does a fresh clone — use `load_cached_repo_context` first if you
    want to reuse an existing ingestion."""
    org, repo = validate_github_url(url)

    with clone_repo_to_sandbox(url) as sandbox_dir:
        commit_sha = get_commit_sha(sandbox_dir)
        cache_dir = repo_cache_dir(org, repo, commit_sha)

        persistent_clone = cloned_repo_path(cache_dir)
        if persistent_clone.exists():
            shutil.rmtree(persistent_clone)
        shutil.copytree(sandbox_dir, persistent_clone, ignore=shutil.ignore_patterns(".git"))

    return _build_context_from_directory(persistent_clone, org, repo, url, commit_sha, cache_dir)


def ingest_local_directory(path: Path, label: str = "local") -> RepoContext:
    """Build a RepoContext directly from an already-on-disk directory — no cloning, no network.

    For pointing OnboardAgent at a repo you already have checked out, and for tests/evals that
    need a real end-to-end ingestion without depending on GitHub access. `path`'s contents are
    only ever read/parsed, never executed, same as a cloned repo.
    """
    path = path.resolve()
    cache_dir = repo_cache_dir("local", label, "local")
    repo_url = f"file://{path}"
    return _build_context_from_directory(path, "local", label, repo_url, "local", cache_dir)


def find_cached_repo_dir(org: str, repo: str) -> Path | None:
    from onboard_agent.cache import cache_root

    repos_dir = cache_root() / "repos"
    if not repos_dir.is_dir():
        return None
    matches = sorted(
        repos_dir.glob(f"{org}__{repo}__*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def load_cached_repo_context(org: str, repo: str) -> RepoContext | None:
    """Reload a previously-ingested repo without re-cloning or re-embedding: chunks and the
    dense vector index are read back from disk; the (cheap) lexical index is rebuilt in
    memory."""
    cache_dir = find_cached_repo_dir(org, repo)
    if cache_dir is None:
        return None

    chunks_file = chunks_path(cache_dir)
    map_file = repo_map_path(cache_dir)
    if not chunks_file.exists() or not map_file.exists():
        return None

    chunks = _read_chunks(chunks_file)
    repo_map = RepoMap.model_validate_json(map_file.read_text(encoding="utf-8"))

    vector_store = VectorStore(lancedb_path(cache_dir))
    if not vector_store.load():
        return None

    lexical_index = LexicalIndex()
    lexical_index.build(chunks)

    retriever = HybridRetriever(vector_store, lexical_index)
    retriever.attach_chunk_registry(chunks)

    return RepoContext(
        org=org,
        repo=repo,
        commit_sha=repo_map.commit_sha,
        repo_root=cloned_repo_path(cache_dir),
        chunks=chunks,
        repo_map=repo_map,
        retriever=retriever,
    )


def get_or_ingest_repo_context(url: str) -> RepoContext:
    org, repo = validate_github_url(url)
    cached = load_cached_repo_context(org, repo)
    if cached is not None:
        return cached
    return ingest_repo(url)
