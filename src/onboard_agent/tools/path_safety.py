"""Shared path-confinement check for any tool that takes a path from external input (a model
tool call, an MCP client). Every such path must resolve to somewhere inside the repo root before
touching disk — mirrors the text-editor tool's security guidance for model-supplied paths."""

from __future__ import annotations

from pathlib import Path


class PathEscapesRepoError(ValueError):
    pass


def resolve_within_repo(repo_root: Path, relative_path: str) -> Path:
    """Resolve `relative_path` against `repo_root` and verify the result stays inside it.
    Rejects absolute paths, `..` traversal, and symlinks that escape the root."""
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise PathEscapesRepoError(f"Absolute paths are not allowed: {relative_path}")

    resolved_root = repo_root.resolve()
    resolved_target = (resolved_root / candidate).resolve()

    if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
        raise PathEscapesRepoError(f"Path escapes the repo root: {relative_path}")

    return resolved_target
