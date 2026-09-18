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
- [x] evals/fixtures/{requests,flask}.yaml, evals/harness.py, evals/metrics.py
- [x] Verify: `uv run` eval command prints metrics table, writes EVALS.md
- [x] Commit + push

## Phase 6 — Finalize
- [x] README.md
- [x] Fresh clone + `uv sync` + full test suite reproduces (eval verified separately across
      multiple live runs against real repos, incl. a genuinely unseen one)
- [x] Final commit + push: `docs: finalize OnboardAgent v1`

# Phase 2 (docs/PHASE2.md)

## Step 0 — docs/ reorg
- [x] Move kickoff.md, PHASE2.md, PLAN.md, TODO.md, EVALS.md into docs/ via `git mv`
- [x] Fix cli/main.py's hardcoded EVALS.md write path
- [x] Update cross-references across the repo
- [x] Commit + push: `chore: move planning docs into docs/`

## Phase 1 — Prove the core
- [x] Ingest 2 new real repos: pallets/click, arrow-py/arrow (flask/requests reused from v1)
- [x] Ground-truth research via `explore` subagent dispatches (4 repos, 8 dispatches total incl.
      extensions to flask/requests)
- [x] Failure taxonomy: evals/taxonomy.py (FailureLabel, QuestionResult, summarize_taxonomy),
      harness.py additions (classify_question_result, run_taxonomy_eval), tests/unit/test_taxonomy.py
- [x] Write/extend all 4 fixture YAMLs (flask 11, requests 11, click 12, arrow 12 questions)
- [x] Baseline measurement (pre-fix, v1 rerank code) across all 4 repos via git-stash
- [x] Fix 1: subword-tokenized identifier/filename-stem matching in indexing/hybrid.py
- [x] Fix 2: system-prompt nudge to use list_structure+read_file for config/tooling questions
- [x] Fix 3: categorical test-file demotion in rerank (test files were winning on identifier
      match against their own test function names)
- [x] Fix 2-correction: suppress filename-stem bonus when stem repeats its parent dir (fixed a
      measured arrow-py/arrow regression from Fix 1)
- [x] Fix 4 (major): `MAX_TOOL_ITERATIONS` raised 8 -> 20 (`agent/loop.py`) — the eval had exposed
      8/33 answerable questions across flask/requests/click coming back with ZERO citations
      because Tool Runner hit the cap mid-plan on multi-file questions and returned a stray
      preamble sentence instead of a synthesized answer. Verified live before/after on one
      question (0 citations -> 17, all grounded).
- [x] Live-answer taxonomy eval, post-iteration-fix: all 4 repos complete — incorrectly_refused
      dropped to 0 across all of them (was 4/9 flask, 3/9 requests, 1/10 click, 0/10 arrow before
      the fix)
- [x] Write docs/EVALS.md Phase 2 section (baseline/fix/after tables + taxonomy breakdown)
- [x] docs/PLAN.md decisions #21 (test-file/identifier rerank fixes), #22 (self-named-module
      correction + prompt nudge), #23 (MAX_TOOL_ITERATIONS fix)
- [x] Full `pytest -q` + commit: `test: baseline + improve core retrieval across real repos`

## Phase 2 — generate_overview
- [ ] Not started

## Phase 3 — Thin Streamlit UI
- [ ] Not started

## Phase 4 — MCP dogfood + finalize
- [ ] Not started
