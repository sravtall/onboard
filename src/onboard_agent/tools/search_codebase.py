"""search_codebase: hybrid retrieval over an ingested repo's chunks. The single implementation
used by both the Tool Runner agent (agent/loop.py) and the MCP server (mcp_server/server.py)."""

from __future__ import annotations

from onboard_agent.ingestion.pipeline import RepoContext
from onboard_agent.tools.schemas import SearchCodebaseInput, SearchCodebaseOutput, SearchResult

_SNIPPET_MAX_CHARS = 800


def search_codebase(input: SearchCodebaseInput, ctx: RepoContext) -> SearchCodebaseOutput:
    results = ctx.retriever.search(input.query, final_k=input.top_k)
    return SearchCodebaseOutput(
        results=[
            SearchResult(
                file_path=r.chunk.file_path,
                start_line=r.chunk.start_line,
                end_line=r.chunk.end_line,
                symbol=r.chunk.symbol,
                kind=r.chunk.kind,
                score=r.score,
                snippet=r.chunk.code_text[:_SNIPPET_MAX_CHARS],
                citation=r.chunk.citation(),
            )
            for r in results
        ]
    )
