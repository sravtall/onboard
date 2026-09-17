"""Integration test: drive the MCP server over real stdio transport with a client, proving the
MCPServer scaffold starts and tools are callable through the protocol (not just as Python
functions)."""

import sys

import pytest
from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

SERVER_MODULE = "onboard_agent.mcp_server.server"


@pytest.mark.asyncio
async def test_hello_tool_is_registered_and_callable():
    params = StdioServerParameters(command=sys.executable, args=["-m", SERVER_MODULE])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = {tool.name for tool in tools.tools}
            assert "hello" in tool_names

            result = await session.call_tool("hello", {"name": "OnboardAgent"})
            text = "".join(
                block.text for block in result.content if getattr(block, "type", None) == "text"
            )
            assert "Hello, OnboardAgent" in text
