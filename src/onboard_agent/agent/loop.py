"""The answering agent: an Anthropic Tool Runner loop over the three retrieval tools, producing
a grounded, cited answer. PLAN.md decision #8 explains why Tool Runner over a manual loop or
Managed Agents.

ask_onboarding_question is the single entry point — it is itself the 4th tool exposed by the
MCP server (mcp_server/server.py imports and calls it directly), never reimplemented there.
"""

from __future__ import annotations

import anthropic
from anthropic import beta_tool
from pydantic import BaseModel

from onboard_agent.agent.grounding import RetrievedSpan, verify_answer
from onboard_agent.agent.prompts import build_system_blocks
from onboard_agent.config import agent_model
from onboard_agent.ingestion.pipeline import RepoContext
from onboard_agent.tools.list_structure import list_structure as _list_structure_impl
from onboard_agent.tools.read_file import read_file as _read_file_impl
from onboard_agent.tools.schemas import (
    ListStructureInput,
    ReadFileInput,
    ReadFileOutput,
    SearchCodebaseInput,
)
from onboard_agent.tools.search_codebase import search_codebase as _search_codebase_impl

MAX_TOOL_ITERATIONS = 8
MAX_ANSWER_TOKENS = 16000


class AnswerResult(BaseModel):
    question: str
    answer: str
    citations: list[str]
    verified: bool
    unverified_citations: list[str]


def _build_tools(ctx: RepoContext, retrieved: list[RetrievedSpan]) -> list:
    @beta_tool
    def search_codebase(query: str, top_k: int = 5) -> str:
        """Search the codebase with hybrid semantic + keyword search.

        Args:
            query: A natural-language question or an exact identifier to search for.
            top_k: Maximum number of results to return (1-20).
        """
        result = _search_codebase_impl(SearchCodebaseInput(query=query, top_k=top_k), ctx)
        for r in result.results:
            retrieved.append(RetrievedSpan(r.file_path, r.start_line, r.end_line))
        return result.model_dump_json()

    @beta_tool
    def read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """Read an exact line range (or the whole file) from the repo.

        Args:
            path: Path relative to the repo root.
            start_line: 1-indexed first line to read, inclusive. Omit for the start of the file.
            end_line: 1-indexed last line to read, inclusive. Omit for the end of the file.
        """
        result = _read_file_impl(
            ReadFileInput(path=path, start_line=start_line, end_line=end_line), ctx
        )
        if isinstance(result, ReadFileOutput):
            retrieved.append(RetrievedSpan(result.path, result.start_line, result.end_line))
        return result.model_dump_json()

    @beta_tool
    def list_structure(path: str = ".") -> str:
        """List a directory's immediate files/subdirectories and each file's top-level symbols.

        Args:
            path: Directory path relative to the repo root. Defaults to the repo root.
        """
        result = _list_structure_impl(ListStructureInput(path=path), ctx)
        return result.model_dump_json()

    return [search_codebase, read_file, list_structure]


def ask_onboarding_question(question: str, ctx: RepoContext) -> AnswerResult:
    retrieved: list[RetrievedSpan] = []
    tools = _build_tools(ctx, retrieved)

    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=agent_model(),
        max_tokens=MAX_ANSWER_TOKENS,
        max_iterations=MAX_TOOL_ITERATIONS,
        tools=tools,
        system=build_system_blocks(ctx.repo_map),
        messages=[{"role": "user", "content": question}],
    )

    final_message = None
    for message in runner:
        final_message = message

    answer_text = ""
    if final_message is not None:
        answer_text = "".join(block.text for block in final_message.content if block.type == "text")

    report = verify_answer(answer_text, ctx.repo_root, retrieved)
    return AnswerResult(
        question=question,
        answer=answer_text,
        citations=[c.as_str() for c in report.citations],
        verified=report.verified,
        unverified_citations=[c.as_str() for c in report.unverified_citations],
    )
