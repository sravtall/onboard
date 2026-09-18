"""generate_overview: a structured, cited onboarding doc for a whole repo, analogous to
agent/loop.py's ask_onboarding_question but for "give me the lay of the land" rather than a
single question. Reuses loop.py's tool wiring (build_tools) and grounding.py's verification
unchanged -- this module owns only the overview-specific prompt and output shape.

Uses the Tool Runner's `output_format` structured-output support (verified against the installed
Anthropic SDK, docs/PLAN.md decision #24) rather than a custom "submit" tool: the model explores
via the three read-only tools as usual, then produces its final answer as JSON matching
OverviewContent instead of free text, available on the final message's `.parsed_output`.
"""

from __future__ import annotations

import anthropic

from onboard_agent.agent.grounding import RetrievedSpan, verify_answer
from onboard_agent.agent.loop import MAX_ANSWER_TOKENS, build_tools
from onboard_agent.agent.prompts import build_overview_system_blocks
from onboard_agent.config import agent_model
from onboard_agent.ingestion.pipeline import RepoContext
from onboard_agent.tools.schemas import GenerateOverviewOutput, OverviewContent

MAX_OVERVIEW_ITERATIONS = 30
"""Higher than agent/loop.py's MAX_TOOL_ITERATIONS (20): a comprehensive multi-section overview
covering architecture, key modules, entry points, and setup legitimately needs to visit more
files than answering one question. Confirmed empirically -- a live Haiku run hit exactly this
cap with 20 iterations (no final text block, parsed_output None) while a second, similar run
completed cleanly in 15 (docs/PLAN.md decision #24)."""


def _flatten_for_grounding(content: OverviewContent) -> str:
    sections = "\n".join(f"{s.heading}\n{s.content}" for s in content.key_modules)
    return "\n".join(
        [
            content.architecture_summary,
            sections,
            content.directory_map,
            "\n".join(content.entry_points),
            content.how_to_run_and_test,
            content.where_to_start,
        ]
    )


def generate_overview(ctx: RepoContext, focus: str | None = None) -> GenerateOverviewOutput:
    retrieved: list[RetrievedSpan] = []
    tools = build_tools(ctx, retrieved)

    prompt = "Generate a comprehensive onboarding overview of this codebase."
    if focus:
        prompt += f" Pay special attention to: {focus}"

    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=agent_model(),
        max_tokens=MAX_ANSWER_TOKENS,
        max_iterations=MAX_OVERVIEW_ITERATIONS,
        tools=tools,
        output_format=OverviewContent,
        system=build_overview_system_blocks(ctx.repo_map),
        messages=[{"role": "user", "content": prompt}],
    )

    final_message = None
    for message in runner:
        final_message = message

    content = final_message.parsed_output if final_message is not None else None
    if content is None:
        content = OverviewContent(
            architecture_summary="",
            key_modules=[],
            directory_map="",
            entry_points=[],
            how_to_run_and_test="",
            where_to_start="",
        )

    report = verify_answer(_flatten_for_grounding(content), ctx.repo_root, retrieved)
    return GenerateOverviewOutput(
        architecture_summary=content.architecture_summary,
        key_modules=content.key_modules,
        directory_map=content.directory_map,
        entry_points=content.entry_points,
        how_to_run_and_test=content.how_to_run_and_test,
        where_to_start=content.where_to_start,
        citations=[c.as_str() for c in report.citations],
        verified=report.verified,
        unverified_citations=[c.as_str() for c in report.unverified_citations],
        retrieved_files=sorted({span.file_path for span in retrieved}),
    )
