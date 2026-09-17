"""Typed input/output models for the read-only tools. These schemas are what an agent (or an
MCP client) sees when deciding whether and how to call a tool — keep field descriptions
precise, per .claude/skills/add-retrieval-tool/SKILL.md."""

from __future__ import annotations

from pydantic import BaseModel, Field

from onboard_agent.chunking.models import ChunkKind


class SearchCodebaseInput(BaseModel):
    query: str = Field(
        description="A natural-language question or an exact identifier to search for"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of results to return")


class SearchResult(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    symbol: str
    kind: ChunkKind
    score: float
    snippet: str = Field(description="The chunk's code text, possibly truncated for display")
    citation: str = Field(description="'file_path:start_line-end_line', ready to show a user")


class SearchCodebaseOutput(BaseModel):
    results: list[SearchResult]


class ReadFileInput(BaseModel):
    path: str = Field(description="Path relative to the repo root")
    start_line: int | None = Field(default=None, ge=1, description="1-indexed, inclusive")
    end_line: int | None = Field(default=None, ge=1, description="1-indexed, inclusive")


class ReadFileOutput(BaseModel):
    path: str
    start_line: int
    end_line: int
    content: str


class ToolError(BaseModel):
    """Generic error result shared by every tool (invalid/escaping path, missing file, etc.)."""

    error: str


class ListStructureInput(BaseModel):
    path: str = Field(default=".", description="Directory path relative to the repo root")


class StructureEntry(BaseModel):
    path: str
    is_directory: bool
    symbols: list[str] = Field(
        default_factory=list, description="Top-level symbols in this file (empty for directories)"
    )


class ListStructureOutput(BaseModel):
    path: str
    entries: list[StructureEntry]
