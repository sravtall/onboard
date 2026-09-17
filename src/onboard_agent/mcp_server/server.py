"""MCP server for OnboardAgent.

Phase 0: a trivial hello-tool proving the MCPServer scaffold starts and a client can call it.
Phase 4 replaces/extends this with the real tools (search_codebase, read_file, list_structure,
ask_onboarding_question), each a thin adapter over src/onboard_agent/tools/ and agent/loop.py —
never a reimplementation.
"""

from mcp.server import MCPServer

mcp = MCPServer("onboard-agent")


@mcp.tool()
def hello(name: str = "world") -> str:
    """Trivial scaffold-verification tool. Returns a greeting; proves the server is wired up."""
    return f"Hello, {name}! OnboardAgent MCP server is running."


if __name__ == "__main__":
    mcp.run()
