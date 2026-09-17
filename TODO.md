# OnboardAgent — TODO

Phases per `kickoff.md` / `PLAN.md`. Check off as exit criteria pass.

## Phase 0 — Claude Code scaffolding
- [x] CLAUDE.md
- [x] .claude/agents/{explore,code-reviewer,test-author}.md
- [x] .claude/hooks/{post_tool_use_format,stop_run_tests,pre_tool_use_path_guard}.py + settings.json
- [x] .mcp.json + trivial MCPServer hello-tool
- [x] .claude/skills/add-retrieval-tool/SKILL.md
- [x] Verify: hook fires on a real edit; hello-tool callable from a minimal MCP client script
- [x] Commit + push: `chore: scaffold Claude Code project`

## Phase 1 — Ingestion & chunking
- [x] ingestion/clone.py (sandboxed temp-dir clone, no code execution)
- [x] ingestion/repo_map.py (README/deps/dir-tree/entry-points)
- [x] chunking/models.py, treesitter_parser.py, chunker.py
- [x] tests/fixtures/tiny_repo/ (+ canary file)
- [x] Verify: chunk boundaries align to def/class; canary never executes
- [x] Commit + push

## Phase 2 — Hybrid indexing & retrieval
- [x] indexing/embeddings.py, vector_store.py, lexical.py, hybrid.py
- [x] Verify: exact-identifier query + paraphrased query both surface right chunk; RRF unit tests
- [x] Commit + push

## Phase 3 — Answering agent
- [x] tools/{schemas,search_codebase,read_file,list_structure}.py
- [x] agent/{prompts,loop,grounding}.py
- [x] Verify (requires ANTHROPIC_API_KEY): cited grounded answer; honest refusal on unanswerable question
- [x] Commit + push

## Phase 4 — MCP server + CLI
- [x] mcp_server/server.py (4 tools) + cli/main.py (ingest/ask/serve-mcp/eval)
- [x] Verify: MCP client lists 4 tools and calls them; CLI answers a real question with citations
- [x] Commit + push

## Phase 5 — Evals
- [ ] evals/fixtures/{requests,flask}.yaml, evals/harness.py, evals/metrics.py
- [ ] Verify: `uv run` eval command prints metrics table, writes EVALS.md
- [ ] Commit + push

## Phase 6 — Finalize
- [ ] README.md
- [ ] Fresh clone + `uv sync` + full test/eval suite reproduces
- [ ] Final commit + push: `docs: finalize OnboardAgent v1`
