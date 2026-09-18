# OnboardAgent — Claude Code autonomous build brief

> **How to use this file.** Create an empty git repo, drop this file in as `KICKOFF.md`,
> open Claude Code in that directory, and send: *"Read KICKOFF.md and execute it end to
> end. Follow the operating protocol exactly."* Then let it run. Run in plan mode first if
> you want to review the plan before it builds; switch to auto-accept edits once you're
> comfortable — the hooks and scoped permissions in Phase 0 are your safety net.

---

## 1. Mission

Build **OnboardAgent**: a tool that, given a public GitHub URL for a **Python** repository,
ingests the codebase, builds a searchable index, and answers a new engineer's **onboarding
questions** — "how does auth work here?", "where do I add an endpoint?", "what's the test
setup?", "trace the request lifecycle" — with **citations to specific files and line
ranges**. The goal is *complete read-only understanding of an unfamiliar codebase*.

This is a greenfield project. Build it to completion autonomously.

## 2. Operating protocol — act as a staff-level engineer who automates everything

You are running as an autonomous senior engineer. Behave accordingly:

- **Plan before building.** First produce `PLAN.md` (architecture, phases, decisions) and a
  `TODO.md` checklist. Persist everything important to disk as you go — treat files as your
  durable memory across context compaction. Update `TODO.md` continuously.
- **Work in phases, and self-verify each one.** Do not advance to the next phase until the
  current phase's **exit criteria** (defined below) pass. You own the verification — write
  and run the tests/evals yourself; don't wait for a human to check.
- **Delegate to subagents** for isolated or parallel work (exploring baseline repos, writing
  tests, reviewing code). Set these up in Phase 0 and use them throughout.
- **Prefer deterministic checks over judgment.** Wire hooks so formatting and tests run
  automatically; let them catch mistakes so you don't have to reason about style/regressions.
- **Only stop and ask the human if truly blocked** — a missing secret you cannot obtain, an
  ambiguous product decision with no reasonable default, or an external service that requires
  their account. For everything else, choose the sensible default, record the decision in
  `PLAN.md` under "Decisions," and keep going.
- **Verify current facts; don't trust your priors.** Libraries below have moved recently.
  Before writing against any SDK, check its current version and API (see the accuracy note
  in Phase 2). When docs are needed, fetch them rather than guessing.
- **Leave a trail.** Conventional commits at each phase boundary. Anyone should be able to
  read the git history and see the project take shape.

## 3. Scope — hold this line

**In scope (v1):** read-only understanding of **Python** repos; ingestion, indexing,
retrieval, and cited question-answering; an MCP server exposing the read-only tools; an eval
harness; a CLI and/or a thin API to ask questions.

**Explicitly out of scope (record as "v2 / next steps," do not build):** writing or
proposing code changes; non-Python languages; a fancy web UI; multi-repo support;
fine-tuning. If you find yourself tempted, note it in `PLAN.md` under "Future work" and move
on. Scope discipline is part of the job.

## 4. Phase 0 — set up the Claude Code machinery (do this first)

Before any application code, configure this repo as a properly-instrumented Claude Code
project. Verify each primitive's current format against the live docs
(https://docs.claude.com/en/docs/claude-code/overview) — schemas change.

1. **`CLAUDE.md`** — the always-loaded constitution: Python 3.12+, `uv` for everything
   (never bare `pip`), `ruff` for format/lint, `pytest` for tests, `src/` layout,
   snake_case, typed data via Pydantic/dataclasses, secrets via `.env` (never committed),
   conventional commits. Keep it lean — sometimes-knowledge goes in skills, not here.
2. **Subagents** (`.claude/agents/`), each with a sharp `description` (the auto-trigger) and
   **scoped tools** (the security control):
   - `explore` — reads baseline repos and this codebase to answer questions in an isolated
     context; **read-only tools** (Read, Grep, Glob).
   - `code-reviewer` — reviews changes against `CLAUDE.md`; **read-only tools**; reports, does
     not edit.
   - `test-author` — writes pytest tests for a given module; can write only under `tests/`.
3. **Hooks** (`.claude/hooks/` wired in `.claude/settings.json`):
   - PostToolUse (Write|Edit) → run `ruff format` + `ruff check --fix`.
   - Stop → run `pytest -q`; a failing suite means the task isn't done.
   - PreToolUse (Write|Edit) → block writes whose path resolves outside this repo.
   - Set a `permissions` deny-list: no `rm -rf`, no reading `.env`, and — because you will
     clone untrusted repos — **all repo cloning and analysis must happen inside a sandboxed
     temp directory, never executing the cloned code.**
4. **MCP server scaffold** (`.mcp.json` + a server module) — you'll implement the tools in
   Phase 4; scaffold the wiring now so the project is MCP-native from the start.
5. **Skill** (`.claude/skills/`) — author one skill, `add-retrieval-tool`, encoding the repo's
   procedure for adding a new read-only analysis tool (schema → implement → test → register
   in the MCP server → document), so the pattern is reusable and consistent.

**Exit criteria:** `CLAUDE.md`, three subagents, three hooks, `settings.json`, `.mcp.json`
scaffold, and one skill all exist; a trivial "hello" tool proves the MCP server starts and a
client can call it; hooks fire on a test edit. Commit: `chore: scaffold Claude Code project`.

## 5. Phase 1 — ingestion & code-aware chunking

Clone a target Python repo **into a sandboxed temp dir** and parse it into chunks that
respect code structure — split by **function/class using an AST**, not fixed size. Preserve
metadata on every chunk: file path, symbol name, start/end line, and a short summary.

- Use **tree-sitter** (language-aware parsing) for robust structure-aware chunking; study
  how **Aider** builds its tree-sitter "repo map" as a proven baseline (see §9).
- Also capture repo-level signals: the README, the dependency/config files, the directory
  tree, and entry points — an onboarding tool needs the map, not just the pieces.

**Exit criteria:** given a repo URL, produce structured chunks with correct file+line
metadata; a test asserts chunk boundaries align to function/class definitions on a fixture
repo. Commit.

## 6. Phase 2 — index & retrieval (hybrid, cited)

Embed the chunks and build retrieval that returns the right code with **exact file+line
citations**.

- Store vectors in a local store (pgvector if Postgres is trivial, else a local option like
  Chroma/LanceDB — pick one and justify it in `PLAN.md`).
- Implement **hybrid retrieval**: dense (embeddings) + lexical (BM25) fused with RRF, because
  code is full of exact identifiers embeddings blur (function names, error strings). Add a
  reranking step (retrieve wide, keep the top few).
- Every retrieved result carries its file path and line range so answers can cite precisely.

> **Accuracy note — verify before coding.** The MCP Python SDK is now **v2** (supports the
> 2026-07-28 spec); the old `FastMCP` class is now **`MCPServer`** in the official SDK, and
> `pip install mcp` resolves to 2.x. The standalone FastMCP project is separately at v3.
> Before writing the server (Phase 4) *or* choosing embedding/vector libs here, check each
> library's current version and API from its docs — do not write against remembered APIs.

**Exit criteria:** a retrieval call returns relevant chunks with accurate citations on the
fixture repo; a small retrieval test passes. Commit.

## 7. Phase 3 — the answering agent

An agent loop that, given an onboarding question, decides what to retrieve (possibly
iteratively — read, realize it needs the config too, search again), assembles context, and
produces a **grounded, cited answer**. It must refuse/insufficiency-flag when the codebase
doesn't contain the answer rather than hallucinate. No code-writing tools — read-only.

**Exit criteria:** end-to-end question → retrieval → cited answer on the fixture repo; answers
cite real files/lines that actually contain the referenced code. Commit.

## 8. Phase 4 — expose everything over MCP + an interface

Implement the read-only tools on the MCP server (verify current SDK API per §6's note):
`search_codebase(query)`, `read_file(path, line_range)`, `list_structure(path)`,
`ask_onboarding_question(question)`. Add a thin CLI (and optionally a minimal API) so a human
can point it at a repo and ask questions. Confirm the server works from at least one MCP
client.

**Exit criteria:** the tools are callable over MCP; the CLI answers a question about a real
repo with citations. Commit.

## 9. Phase 5 — evals (prove it works)

Build an eval harness with a fixed set of onboarding questions per fixture repo, each with a
known-good answer / known relevant files. Score **retrieval accuracy** (did the right files
come back?) and **answer groundedness** (is every claim backed by cited code?). Produce a
short results table. Include questions the repo *can't* answer, to test honest refusal.

**Exit criteria:** `uv run <eval command>` prints a metrics table; results are recorded in
`EVALS.md`. Commit.

## 10. Phase 6 — finalize

Write `README.md` (what it is, setup, how to run, architecture diagram, eval results,
explicit v2/next-steps). Ensure a fresh clone + `uv sync` reproduces the environment and the
full test + eval suite passes. Final commit: `docs: finalize OnboardAgent v1`.

## 11. Baseline repos to study (via the `explore` subagent)

Study these for proven patterns before/while building. **Verify each is current and
well-maintained; prefer the actively-maintained one if a pattern has several implementations.**

- **`modelcontextprotocol/python-sdk`** — the official MCP SDK (now v2; note `MCPServer`).
  The canonical server/tool/resource patterns.
- **`modelcontextprotocol/servers`** — reference MCP servers; study how mature servers
  structure tools, schemas, and errors.
- **`Aider-AI/aider`** — its tree-sitter **repo map** is the reference pattern for giving an
  agent structural understanding of a codebase. Study this closely for Phase 1.
- **`tree-sitter/tree-sitter`** — the AST parsing engine; find the Python grammar bindings.
- For hybrid code retrieval, review how established code-search tools (e.g., Sourcegraph's
  approach) and the LangChain/LlamaIndex **code splitters** handle language-aware chunking —
  adopt the ideas, keep the implementation yours and minimal.

Take patterns, not code. Attribute anything you adapt. Keep the build lean and original.

## 12. Definition of done (self-check before declaring completion)

- [ ] Phase 0 machinery all present and functioning (subagents, hooks, MCP, skill, CLAUDE.md)
- [ ] Point it at an arbitrary **Python** GitHub repo it hasn't seen → get cited, grounded
      answers to onboarding questions
- [ ] Structure-aware (AST) chunking with correct file+line citations
- [ ] Hybrid retrieval + reranking, retrieval + answer tests passing
- [ ] Read-only MCP server with the four tools, callable from a client
- [ ] Eval harness with a metrics table in `EVALS.md`, including refusal cases
- [ ] Untrusted repos are cloned into a sandbox and never executed
- [ ] `README.md`, `PLAN.md`, `TODO.md` complete; fresh clone reproduces and all checks pass
- [ ] Clean conventional-commit history telling the build story

When every box is checked and the suite is green, summarize what you built, the eval numbers,
the decisions you made autonomously, and the v2/next-steps — then stop.

## 13. If you get blocked

Stop and ask the human **only** for: a secret/credential you cannot obtain, a product
decision with no reasonable default, or an external account you can't create. State the
blocker, the options, and your recommended default. Otherwise: choose, record the decision in
`PLAN.md`, and continue.
