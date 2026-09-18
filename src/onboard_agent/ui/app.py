"""Thin Streamlit demo UI: ingest a repo, ask questions or generate an overview, expand citations
to see the exact retrieved code. No business logic here -- every call goes straight into
ingestion.pipeline / agent.loop / agent.overview / tools.read_file, the same functions the CLI
and MCP server use (see docs/CLAUDE.md's architecture invariant). Run with:

    uv run streamlit run src/onboard_agent/ui/app.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from onboard_agent.agent.loop import AnswerResult, ask_onboarding_question
from onboard_agent.agent.overview import generate_overview
from onboard_agent.ingestion.pipeline import (
    RepoContext,
    get_or_ingest_repo_context,
    ingest_local_directory,
)
from onboard_agent.tools.read_file import read_file
from onboard_agent.tools.schemas import GenerateOverviewOutput, ReadFileInput, ReadFileOutput

st.set_page_config(page_title="OnboardAgent", page_icon="\U0001f4d6", layout="wide")

if "ctx" not in st.session_state:
    st.session_state.ctx = None


def _render_citation(ctx: RepoContext, citation: str) -> None:
    """Expand-on-demand: a citation only resolves to a code snippet when the user opens it,
    via a real read_file call -- the same tool the agent itself uses, never a re-implementation."""
    path, _, line_range = citation.rpartition(":")
    start_str, _, end_str = line_range.partition("-")
    with st.expander(citation):
        try:
            start, end = int(start_str), int(end_str)
        except ValueError:
            st.code(f"Could not parse citation: {citation}")
            return
        result = read_file(ReadFileInput(path=path, start_line=start, end_line=end), ctx)
        if isinstance(result, ReadFileOutput):
            language = "python" if path.endswith(".py") else None
            st.code(result.content, language=language, line_numbers=True)
        else:
            st.error(result.error)


def _render_verification(citations: list[str], verified: bool, unverified: list[str]) -> None:
    if not citations:
        st.info("No citations in this answer.")
        return
    if verified:
        st.success(f"All {len(citations)} citations verified against retrieved code.")
    else:
        st.warning(f"{len(unverified)} of {len(citations)} citations could not be verified.")


def _render_provenance(retrieved_files: list[str]) -> None:
    if not retrieved_files:
        return
    with st.expander(f"Retrieval provenance: {len(retrieved_files)} file(s) searched this session"):
        for f in retrieved_files:
            st.text(f)


def _render_answer(ctx: RepoContext, result: AnswerResult) -> None:
    st.markdown(result.answer)
    _render_verification(result.citations, result.verified, result.unverified_citations)
    for citation in result.citations:
        _render_citation(ctx, citation)
    _render_provenance(result.retrieved_files)


def _render_overview(ctx: RepoContext, result: GenerateOverviewOutput) -> None:
    st.subheader("Architecture")
    st.markdown(result.architecture_summary)

    st.subheader("Key modules")
    for section in result.key_modules:
        st.markdown(f"**{section.heading}**")
        st.markdown(section.content)

    st.subheader("Directory map")
    st.code(result.directory_map, language=None)

    st.subheader("Entry points")
    for entry in result.entry_points:
        st.markdown(f"- {entry}")

    st.subheader("How to run and test")
    st.markdown(result.how_to_run_and_test)

    st.subheader("Where to start")
    st.markdown(result.where_to_start)

    _render_verification(result.citations, result.verified, result.unverified_citations)
    for citation in result.citations:
        _render_citation(ctx, citation)
    _render_provenance(result.retrieved_files)


st.title("OnboardAgent")
st.caption("Read-only onboarding Q&A for a Python codebase, with citations you can verify.")

with st.sidebar:
    st.header("Ingest a repo")
    repo_url = st.text_input("GitHub repo URL", placeholder="https://github.com/org/repo")
    local_path = st.text_input("...or a local path", placeholder="/path/to/already-cloned/repo")
    if st.button("Ingest", type="primary"):
        if not repo_url and not local_path:
            st.error("Provide a repo URL or a local path.")
        else:
            with st.spinner("Ingesting (clone, chunk, embed)..."):
                st.session_state.ctx = (
                    ingest_local_directory(Path(local_path))
                    if local_path
                    else get_or_ingest_repo_context(repo_url)
                )
            st.rerun()

    ctx = st.session_state.ctx
    if ctx is not None:
        st.success(
            f"Ingested {ctx.org}/{ctx.repo} @ {ctx.commit_sha[:12]} ({len(ctx.chunks)} chunks)"
        )

ctx = st.session_state.ctx
if ctx is None:
    st.info("Ingest a repo from the sidebar to get started.")
else:
    mode = st.radio("Mode", ["Ask a question", "Generate overview"], horizontal=True)

    if mode == "Ask a question":
        question = st.text_input("Your onboarding question")
        if st.button("Ask") and question:
            with st.spinner("Searching and reading code..."):
                result = ask_onboarding_question(question, ctx)
            _render_answer(ctx, result)

    else:
        focus = st.text_input("Optional focus area", placeholder="e.g. the authentication flow")
        if st.button("Generate overview"):
            with st.spinner("Exploring the codebase..."):
                result = generate_overview(ctx, focus=focus or None)
            _render_overview(ctx, result)
