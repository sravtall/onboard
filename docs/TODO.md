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
- [x] Verified Tool Runner's `output_format` structured-output support against the installed SDK
      (no custom "submit" tool needed)
- [x] Schemas in tools/schemas.py: GenerateOverviewInput, OverviewSection, OverviewContent,
      GenerateOverviewOutput
- [x] agent/overview.py: generate_overview(ctx, focus=None), reusing loop.py's build_tools
      (exported, no duplication) and grounding.py's verify_answer unchanged
- [x] Own MAX_OVERVIEW_ITERATIONS=30 (higher than Q&A's 20) -- found and fixed the same class of
      truncation bug as Phase 1's MAX_TOOL_ITERATIONS fix, this time for the broader overview task
- [x] New system prompt: agent/prompts.py::build_overview_system_blocks
- [x] New CLI command: `onboard overview [--repo|--local-path] [--focus]`
- [x] New MCP tool: generate_overview (tool count 4 -> 5), integration test updated
- [x] Eval extension: overview_check block (all 4 fixtures) + score_overview_accuracy, unit-tested
- [x] Verified live against a real repo (arrow-py/arrow, with --focus): 45 citations, fully grounded
- [x] docs/PLAN.md decisions #24 (output_format usage), #25 (MAX_OVERVIEW_ITERATIONS)
- [x] Full pytest -q -m "not requires_api_key" green (75 passed)
- [ ] Commit: `feat: codebase overview generation`

## Phase 3 — Thin Streamlit UI
- [x] Verified Streamlit's current API (session_state semantics, st.rerun) via docs before writing
- [x] `uv add streamlit` (1.64.0, resolves cleanly on Python 3.12)
- [x] New `ui/` package: `src/onboard_agent/ui/app.py` -- thin adapter only, no new business logic
- [x] Sidebar ingest (repo URL or local path), `st.session_state.ctx` persists across reruns
- [x] Ask-a-question / Generate-overview mode toggle
- [x] Citations render as `st.expander` calling the real `read_file` tool on demand (not a
      re-implementation); verification banner matches CLI wording
- [x] Retrieval-provenance panel -- added `retrieved_files` field to `AnswerResult`/
      `GenerateOverviewOutput` to support it
- [x] Updated CLAUDE.md's architecture-invariant paragraph to name `ui/app.py` as a third thin
      adapter
- [x] docs/PLAN.md decisions #26 (citation-expander interpretation), #27 (retrieved_files field)
- [x] Live-verified in an actual browser: ingested the tiny fixture repo, asked a real question,
      confirmed the answer, "All 6 citations verified" banner, all 6 expandable code snippets, and
      "Retrieval provenance: 3 file(s) searched this session" panel all render correctly
- [ ] Commit: `feat: thin web UI for demos`

## Phase 4 — MCP dogfood + finalize
- [x] Verified `uv run --directory <path>` flag spelling via `uv run --help`
- [x] README: web UI usage section, external MCP registration section with copy-pasteable
      `.mcp.json` snippet, refreshed architecture diagram (agent/overview.py, ui/app.py),
      refreshed eval summary table (Phase 2, all 4 repos), Scope section updated (web UI +
      overview generation now in scope), new honest "Limitations & v2 next-steps" section
- [x] Fixed a real footgun found by hitting it twice this session: `onboard eval` no longer
      overwrites docs/EVALS.md by default -- now requires an explicit `--write-report` flag
      (docs/PLAN.md decision #28)
- [x] Fresh-clone-equivalent reproducibility confirmed: `uv sync`, full `pytest -q` (78 passed,
      including live-API tests), `onboard eval --retrieval-only` all green
- [ ] Commit: `docs: finalize OnboardAgent Phase 2`
