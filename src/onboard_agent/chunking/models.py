"""Typed data models for chunks and the repo-level map."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ChunkKind(StrEnum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


class Chunk(BaseModel):
    """One retrievable unit of code: a module preamble, a class, a function, or a method.

    Line numbers are 1-indexed and inclusive, matching what a human would see in an editor,
    so citations built from a Chunk can be shown directly as `file_path:start_line-end_line`.
    """

    chunk_id: str = Field(description="Stable id: '<relative_file_path>::<symbol_path>'")
    file_path: str = Field(description="Path relative to the repo root")
    symbol: str = Field(
        description="The function/class/method name, or '<module>' for a preamble chunk"
    )
    kind: ChunkKind
    parent_symbol: str | None = Field(
        default=None, description="Enclosing class name, set only when kind is METHOD"
    )
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    code_text: str = Field(description="Raw source text for this chunk's line range")
    summary: str = Field(description="First docstring sentence, or a truncated signature line")

    def citation(self) -> str:
        return f"{self.file_path}:{self.start_line}-{self.end_line}"


class RepoMap(BaseModel):
    """Repo-level signals captured once per ingestion: the map, not just the pieces."""

    repo_url: str
    commit_sha: str
    readme_excerpt: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    directory_tree: str = Field(description="Depth-limited, rendered as indented text")
    entry_points: list[str] = Field(
        default_factory=list, description="Console-script targets, manage.py/app.py/main.py, etc."
    )
