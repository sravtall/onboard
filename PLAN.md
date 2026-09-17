# OnboardAgent — Plan

See `kickoff.md` for the full mission brief and phase exit criteria. This file tracks
architecture and the decisions made while executing it.

## Architecture

```
onboard/
├── src/onboard_agent/
│   ├── config.py                # env vars: ANTHROPIC_API_KEY, ONBOARD_AGENT_MODEL, embed model
│   ├── ingestion/                # sandboxed clone + repo map (README/deps/dir-tree/entry-points)
│   ├── chunking/                 # tree-sitter AST -> Chunk models
│   ├── indexing/                 # LanceDB (dense) + bm25s (lexical) + RRF fusion + rerank
│   ├── tools/                    # ★ single implementation of search_codebase/read_file/list_structure
│   ├── agent/                    # Tool Runner loop + citation grounding verification
│   ├── mcp_server/               # MCP server — thin adapters over tools/ + agent/
│   ├── cli/                      # Typer CLI: ingest / ask / serve-mcp / eval
│   └── evals/                    # eval harness + fixture question sets
└── tests/                        # unit (tiny synthetic fixture repo) + integration
```

The Tool Runner agent (Phase 3) and the MCP server (Phase 4) both call into `tools/` — no
duplicated retrieval/read logic between the two exposure surfaces.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Package manager `uv`, formatter/linter `ruff`, tests `pytest`, `src/` layout | Mandated by kickoff.md |
| 2 | MCP SDK: `mcp` v2.0, `MCPServer` class (not `FastMCP` — old import path removed, not deprecated) | Verified live: `mcp.server.fastmcp` no longer exists in `mcp` 2.x; `MCPServer("name")` + `@mcp.tool()` decorator confirmed against current SDK README |
| 3 | AST parsing: `tree-sitter` + `tree-sitter-python` direct bindings (not `tree-sitter-languages`) | Only Python needed for v1; avoids an extra dependency layer |
| 4 | Vector store: LanceDB | Embedded, no server process (unlike pgvector/Postgres); disk-backed via Arrow/Lance so it scales past RAM (unlike Chroma's memory-first default); simple pip-installable library appropriate for a CLI tool |
| 5 | Embeddings: local via `sentence-transformers`, no external API | Anthropic has no public embeddings API; keeps the tool fully offline with no second provider secret. Model swappable via `ONBOARD_AGENT_EMBED_MODEL`. Voyage AI/OpenAI noted as a v2 upgrade path for higher quality |
| 6 | Lexical: `bm25s`, fused with dense via Reciprocal Rank Fusion (`score = Σ 1/(k+rank)`, k=60) | Code has exact identifiers embeddings blur; kickoff explicitly asks for hybrid + RRF |
| 7 | Reranking: cheap algorithmic rerank (identifier-match bonus, kind-priority nudge), no cross-encoder | Keeps Phase 2 fully testable with no API key. A Haiku-based reranker is a documented, flag-gated v2 option once Phase 3 has API access |
| 8 | Answering agent: Anthropic Tool Runner (`client.beta.messages.tool_runner` + `@beta_tool`) | Right tier for "custom agent with your own tools, without hand-writing the loop"; Managed Agents' hosted sandbox/session model is unwarranted for a local CLI tool; a manual loop would just re-implement what the SDK already gives us |
| 9 | Model: default `claude-opus-5`, overridable via `ONBOARD_AGENT_MODEL` | Current flagship per policy; never silently downgraded, but configurable since this CLI is invoked repeatedly and cost is a real user concern (e.g. `claude-sonnet-5` for cheaper runs) |
| 10 | Prompt caching: per-repo "repo map" (README/deps/dir-tree/entry-points) cached as an `ephemeral` system-prompt block | Reused across every question asked against the same repo in a session |
| 11 | Fixtures: synthetic `tests/fixtures/tiny_repo/` for fast offline unit tests (includes a "canary" file to prove cloned code is never executed) + real repos `psf/requests` and `pallets/flask`, pinned to a commit SHA, for Phase 3-5 integration/evals | Well-documented, moderate size, recognizable auth/routing/testing patterns matching kickoff's example onboarding questions |
| 12 | Sandbox: clone into `tempfile.mkdtemp()` via `git clone --depth 1`, `GIT_TERMINAL_PROMPT=0`, HTTPS-only URL validation | Kickoff's hard security requirement — untrusted repos must never be executed |
| 13 | Git workflow: commit at each phase boundary, push directly to `main` on `github.com/sravtall/onboard` using the user's own git/gh SSH credentials | User's explicit choice — "deploy with my credentials", no PR review requested |

## Future work / v2 (explicitly out of scope for v1)

- Writing or proposing code changes (v1 is read-only).
- Non-Python language support (JS/TS/Go/etc. via additional tree-sitter grammars).
- A web UI (CLI + MCP only for v1).
- Multi-repo support (cross-repo questions).
- Fine-tuning.
- Cross-encoder or LLM-based reranking (v1 uses a cheap algorithmic rerank).
- Cloud/API-based embeddings (Voyage AI, OpenAI) as an optional higher-quality path.
- Corrective re-prompt loop when citation grounding verification fails (v1 surfaces
  `verified: bool` + unverified citations; it does not auto-retry).
- Remote MCP transport (SSE/HTTP) — v1 is stdio only.
