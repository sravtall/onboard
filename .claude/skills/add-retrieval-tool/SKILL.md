---
name: add-retrieval-tool
description: Procedure for adding a new read-only analysis/retrieval tool to OnboardAgent (schema, implementation, tests, MCP registration, docs). Use when the project needs a new read-only tool exposed through both the Tool Runner agent and the MCP server.
---

# Adding a new read-only retrieval tool

OnboardAgent exposes exactly one implementation of each tool, in `src/onboard_agent/tools/`,
reused by both the Tool Runner agent loop (`agent/loop.py`) and the MCP server
(`mcp_server/server.py`). Follow this order — skipping steps causes drift between the two
surfaces.

## 1. Schema

Add a Pydantic input model and output model to `src/onboard_agent/tools/schemas.py`. Keep the
input model's fields minimal and give every field a docstring/description — this text becomes
what the agent sees when deciding whether to call the tool.

## 2. Implement

Add `src/onboard_agent/tools/<tool_name>.py` with a single function:

```python
def <tool_name>(input: <ToolName>Input, ctx: RepoContext) -> <ToolName>Output:
    ...
```

- `ctx: RepoContext` carries the cloned-repo root, the chunk index, and the vector/lexical
  stores — inject it, don't reach for globals.
- **Read-only.** Never write to the cloned repo. Never `import`, `exec`, or subprocess-run
  anything inside it.
- If the tool accepts a `path`, resolve it to canonical form and verify it stays within
  `ctx.repo_root` before touching disk (mirror the existing check in `tools/read_file.py`).
- Every result that references code must carry `file_path`, `start_line`, `end_line` so answers
  can cite it precisely.

## 3. Test

Add `tests/unit/test_<tool_name>.py` against `tests/fixtures/tiny_repo/`. Assert the tool's
output shape and that any path-escape attempt (`../../etc/passwd`, absolute paths outside the
repo) is rejected rather than silently allowed.

## 4. Register

Wire the tool in **both** places — this is the step most likely to be forgotten:

- `agent/loop.py`: wrap it as a `@beta_tool`-decorated function for the Tool Runner.
- `mcp_server/server.py`: register it as an MCP tool via the current `MCPServer` API
  (`@mcp.tool()` as of the v2 SDK — verify against `modelcontextprotocol/python-sdk` if this has
  changed).

Both wrappers should be thin — call straight into `tools/<tool_name>.py`, no logic duplication.

## 5. Document

- Add the tool to the list in `CLAUDE.md`'s architecture invariant section if it's a core
  retrieval primitive.
- Update `README.md`'s tool list (Phase 6) and, if it changes what a citation looks like, note
  it in `docs/PLAN.md`'s Decisions table.
