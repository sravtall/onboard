"""Phase 4 exit criteria: the MCP server's tools are listed and callable over real stdio
transport (not just as Python functions). `search_codebase`/`read_file`/`list_structure` are
exercised with no API key (ONBOARD_AGENT_LOCAL_REPO_PATH points at the fixture repo, skipping
network cloning entirely); `ask_onboarding_question` needs a real API key and is covered
separately."""

import json
import sys
from pathlib import Path

import pytest
from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

from onboard_agent.config import has_api_key

SERVER_MODULE = "onboard_agent.mcp_server.server"
FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "tiny_repo"


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", SERVER_MODULE],
        env={"ONBOARD_AGENT_LOCAL_REPO_PATH": str(FIXTURE_REPO)},
    )


def _text_of(result) -> str:
    return "".join(block.text for block in result.content if getattr(block, "type", None) == "text")


@pytest.mark.asyncio
async def test_all_five_tools_are_registered():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {tool.name for tool in tools.tools}
            assert tool_names == {
                "search_codebase",
                "read_file",
                "list_structure",
                "ask_onboarding_question",
                "generate_overview",
            }


@pytest.mark.asyncio
async def test_search_codebase_over_real_protocol_returns_a_citation():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("search_codebase", {"query": "add_user", "top_k": 3})
            text = _text_of(result)
            assert "classes_and_methods.py" in text
            assert "citation" in text


@pytest.mark.asyncio
async def test_read_file_over_real_protocol_returns_requested_lines():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "read_file",
                {"path": "plain_functions.py", "start_line": 6, "end_line": 8},
            )
            text = _text_of(result)
            assert "def add" in text


@pytest.mark.asyncio
async def test_read_file_over_real_protocol_rejects_path_escape():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("read_file", {"path": "../../etc/passwd"})
            text = _text_of(result)
            assert "error" in text.lower()


@pytest.mark.asyncio
async def test_list_structure_over_real_protocol_lists_symbols():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("list_structure", {"path": "."})
            text = _text_of(result)
            assert "plain_functions.py" in text
            assert "add" in text


@pytest.mark.skipif(not has_api_key(), reason="ANTHROPIC_API_KEY not set")
@pytest.mark.asyncio
async def test_ask_onboarding_question_over_real_protocol_returns_a_grounded_answer():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "ask_onboarding_question", {"question": "How do I register a new user?"}
            )
            payload = json.loads(_text_of(result))
            assert payload["verified"] is True
            assert any("classes_and_methods.py" in c for c in payload["citations"])


@pytest.mark.skipif(not has_api_key(), reason="ANTHROPIC_API_KEY not set")
@pytest.mark.asyncio
async def test_generate_overview_over_real_protocol_returns_a_grounded_overview():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("generate_overview", {})
            payload = json.loads(_text_of(result))
            assert payload["verified"] is True
            assert payload["architecture_summary"]
            assert payload["key_modules"]
