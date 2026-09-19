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


class GenerateOverviewInput(BaseModel):
    focus: str | None = Field(
        default=None,
        description="Optional area to emphasize, e.g. 'the authentication flow' or 'testing setup'",
    )


class OverviewSection(BaseModel):
    heading: str
    content: str = Field(
        description="Prose for this section, with inline citations `path/to/file.py:START-END`"
    )


class OverviewContent(BaseModel):
    """The model-facing structured output schema for generate_overview -- what the model itself
    fills in. `GenerateOverviewOutput` wraps this with grounding-derived fields (citations,
    verified, unverified_citations), the same split `AnswerResult` uses in `agent/loop.py`."""

    architecture_summary: str = Field(description="A few paragraphs on the overall design")
    key_modules: list[OverviewSection] = Field(
        description="One section per major module/package, explaining what it does"
    )
    directory_map: str = Field(description="A short annotated tree of the notable directories")
    entry_points: list[str] = Field(description="Where execution starts, e.g. CLI commands")
    how_to_run_and_test: str = Field(description="How to install, run, and test this project")
    where_to_start: str = Field(description="A concrete suggestion for a new engineer's first read")


class UsageTotals(BaseModel):
    """Accumulated Anthropic API usage across every Tool Runner iteration (one BetaMessage per
    live API call) in a single ask_onboarding_question or generate_overview invocation."""

    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class GenerateOverviewOutput(BaseModel):
    architecture_summary: str
    key_modules: list[OverviewSection]
    directory_map: str
    entry_points: list[str]
    how_to_run_and_test: str
    where_to_start: str
    citations: list[str]
    verified: bool
    unverified_citations: list[str]
    retrieved_files: list[str] = []
    usage: UsageTotals = Field(default_factory=UsageTotals)
