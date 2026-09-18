# OnboardAgent

A read-only onboarding agent for Python codebases. Point it at a public GitHub repo and ask
questions like *"how does auth work here?"*, *"where do I add an endpoint?"*, or *"what's the
test setup?"* — every claim in the answer is backed by a citation to a real `file.py:START-END`
range, and the agent says so explicitly when it can't find something rather than guessing.

Built end to end from [`docs/kickoff.md`](docs/kickoff.md) and [`docs/PHASE2.md`](docs/PHASE2.md);
see [`docs/PLAN.md`](docs/PLAN.md) for the full decision log and [`docs/EVALS.md`](docs/EVALS.md)
for measured results.

## What it does

1. **Ingest** — clones a repo into a sandboxed temp directory, parses every `.py` file with
   tree-sitter into function/class/method/module chunks (never fixed-size text splitting), and
   builds a "repo map" (README, dependencies, directory tree, entry points).
2. **Index** — embeds chunks locally (`sentence-transformers`, no external API), stores vectors
   in LanceDB, and builds a BM25 lexical index — code has exact identifiers embeddings blur.
3. **Retrieve** — fuses dense + lexical rankings via Reciprocal Rank Fusion, then a cheap
   algorithmic rerank narrows to the final citations.
4. **Answer** — an Anthropic Tool Runner agent loop searches, reads, and re-searches as needed,
   then produces a cited answer (or, for `overview`, a structured multi-section onboarding doc).
   Every citation is checked against code the agent actually retrieved that session before being
   returned.
5. **Expose** — the same read-only tools and agents are available as an MCP server (for Claude
   Code, Claude Desktop, or any MCP client), a CLI, and a thin Streamlit demo UI.

Untrusted repo code is **never executed** — only cloned, statically parsed, and read as text.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.12+ (uv will install the interpreter
if needed).

```sh
git clone https://github.com/sravtall/onboard.git
cd onboard
uv sync
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

`ANTHROPIC_API_KEY` is only needed for the answering agent (`onboard ask`, `ask_onboarding_question`,
and evals) — ingestion and raw retrieval (`onboard ingest`, `search_codebase`, `read_file`,
`list_structure`) work with no key at all, since embeddings are local.

## Usage

### CLI

```sh
# Clone + chunk + index a repo (also happens automatically on first `ask`)
uv run onboard ingest https://github.com/psf/requests

# Ask a cited question
uv run onboard ask "How does requests handle authentication?" --repo https://github.com/psf/requests

# Point at a repo you already have checked out (skips cloning)
uv run onboard ask "What's the test setup?" --local-path /path/to/checkout

# Generate a cited onboarding overview of the whole repo
uv run onboard overview --repo https://github.com/psf/requests --focus "how retries work"

# Run the eval harness
uv run onboard eval
```

### Web UI

```sh
uv run streamlit run src/onboard_agent/ui/app.py
```

A one-screen demo: ingest a repo from the sidebar, then ask questions or generate an overview.
Every citation expands in place to the real retrieved code (via the same `read_file` tool the
agent uses), and a "retrieval provenance" panel shows every file the agent searched or read that
session, not just the ones it ended up citing. No business logic lives here — it's a thin adapter
over the same functions the CLI and MCP server call.

### MCP server

```sh
uv run onboard serve-mcp --repo https://github.com/psf/requests
# or, for a local checkout:
uv run onboard serve-mcp --local-path /path/to/checkout
```

Exposes five read-only tools: `search_codebase(query, top_k)`, `read_file(path, start_line,
end_line)`, `list_structure(path)`, `ask_onboarding_question(question)`, and
`generate_overview(focus)`. See [`.mcp.json`](.mcp.json) for a ready-to-use Claude Code
configuration (set `ONBOARD_AGENT_REPO_URL` there to point it at a specific repo).

#### Registering this server from another Claude Code project

Point another project's `.mcp.json` at this repo's server without installing anything globally —
`uv run --directory` runs the command in this project's own environment regardless of your
current working directory:

```json
{
  "mcpServers": {
    "onboard-agent": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/onboard", "onboard", "serve-mcp",
                "--repo", "https://github.com/psf/requests"],
      "env": { "ANTHROPIC_API_KEY": "..." }
    }
  }
}
```

Swap `--repo <url>` for `--local-path <path>` to point at a repo you already have checked out.
The API key only needs to be set here if you want `ask_onboarding_question`/`generate_overview`
available — `search_codebase`/`read_file`/`list_structure` work without one.

### As a Python library

```python
from onboard_agent.ingestion.pipeline import get_or_ingest_repo_context
from onboard_agent.agent.loop import ask_onboarding_question

ctx = get_or_ingest_repo_context("https://github.com/psf/requests")
result = ask_onboarding_question("How does requests implement retries?", ctx)
print(result.answer)
print(result.citations, result.verified)
```

## Architecture

```
                          ┌─────────────────────────────┐
  GitHub URL  ──clone──▶  │  Sandboxed temp directory    │
                          │  (never executed)            │
                          └──────────────┬───────────────┘
                                         │ persisted, read-only
                                         ▼
                          ┌─────────────────────────────┐
                          │  Per-repo cache               │
                          │  ~/.onboard_agent_cache/...    │
                          │  clone/  chunks.jsonl          │
                          │  repo_map.json  lancedb/       │
                          └──────────────┬───────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                          ▼
     chunking/ (tree-sitter)   indexing/ (LanceDB + BM25s)   ingestion/repo_map.py
     function/class/method/     dense + lexical, fused        README, deps,
     module chunks w/ citations via RRF, algorithmic rerank    dir tree, entry points
              │                          │                          │
              └──────────────┬───────────┴──────────────────────────┘
                             ▼
                   tools/  ★ single implementation ★
          search_codebase · read_file · list_structure
                             │
              ┌──────────────┬──────────────┬──────────────┐
              ▼              ▼              ▼              ▼
   agent/loop.py      agent/overview.py  mcp_server/    ui/app.py
   (Tool Runner)       (Tool Runner,      server.py      (Streamlit,
   ask_onboarding_      output_format)    5 tools        thin adapter
   question()          generate_overview()               over loop.py/
   + agent/grounding.py verifies every citation           overview.py)
```

`src/onboard_agent/tools/` is the single implementation of the three retrieval primitives — the
answering agent, the overview generator, the MCP server, and the Streamlit UI are all thin
adapters over it (see `CLAUDE.md`'s architecture invariant). `agent/grounding.py` checks every
citation in an answer against code actually retrieved that session before returning it, surfacing
`verified: bool` and any unverified citations rather than hiding them.

### Key decisions (see [`docs/PLAN.md`](docs/PLAN.md) for the full table with rationale)

- **Vector store:** LanceDB — embedded, disk-backed, no separate server process.
- **Embeddings:** local `sentence-transformers`, no external API/key (Anthropic has no public
  embeddings endpoint).
- **Hybrid retrieval:** dense + BM25 fused via Reciprocal Rank Fusion, then a cheap algorithmic
  rerank (no cross-encoder) so retrieval stays fully testable without an API key.
- **Answering agent:** Anthropic Tool Runner (`client.beta.messages.tool_runner`), not a manual
  loop or Managed Agents — the right tier for a custom-tool agent without hosted-sandbox
  overhead.
- **Model:** `claude-opus-5` by default, overridable via `ONBOARD_AGENT_MODEL`.

## Eval results

See [`docs/EVALS.md`](docs/EVALS.md) for the full before/after tables, a labeled failure taxonomy
(`correct` / `retrieval_miss` / `hallucinated` / `should_refuse_but_didnt` / `incorrectly_refused`),
and honest notes on remaining weak spots and live-model non-determinism. Summary after Phase 2's
real-repo error analysis and fixes, across 4 repos of varying shape:

| Repo | Retrieval Recall@K | Citation Groundedness | Refusal Accuracy |
|---|---|---|---|
| arrow-py/arrow | 100% | 100% | 50% |
| pallets/click | 80% | 99% | 50% |
| pallets/flask | 67% | 100% | 50% |
| psf/requests | 89% | 95% | 100% |

Citation groundedness measures *every citation the agent ever produced* against code it actually
retrieved that session — it is not a proxy metric, it's the safety property the whole project
exists to guarantee. Refusal accuracy is scored on deliberately unanswerable questions (e.g.
"how does this integrate with Stripe?" against a repo with no payment code) — a correct refusal
means no fabricated citation, regardless of exact wording. Phase 2 found and fixed 5 real bugs
this way (3 retrieval-reranking issues, a prompt gap for non-Python config files, and a tool-call
iteration cap that was silently truncating answers) — see `docs/EVALS.md` for the root-cause
analysis behind each one.

## Development

```sh
uv sync                        # install deps (incl. dev group)
uv run ruff format . && uv run ruff check .
uv run pytest -q               # tests needing ANTHROPIC_API_KEY auto-skip if it's unset
uv run onboard eval            # full eval run (clones real repos, calls the live API)
```

Claude Code project scaffolding — subagents, hooks (auto-format on write, path-confinement
guard, pytest gate on stop), and the `add-retrieval-tool` skill for adding new read-only tools —
lives under [`.claude/`](.claude/).

## Scope

**In scope:** read-only understanding of Python repos — ingestion, indexing, hybrid retrieval,
cited question-answering, codebase overview generation, an MCP server, a CLI, a thin demo web UI,
and an eval harness with a labeled failure taxonomy.

**Explicitly out of scope** (see `docs/PLAN.md`'s "Future work" section for the full list and
why):

- Writing or proposing code changes
- Non-Python languages
- Multi-repo support (cross-repo questions)
- Multi-user / auth / cloud deployment
- Fine-tuning
- Cross-encoder/LLM-based reranking, cloud embeddings, a corrective re-prompt loop on failed
  grounding, remote MCP transport, and exact commit-SHA pinning for evals

## Limitations & v2 next-steps

Honestly reported, not fixed in this build (see `docs/EVALS.md`/`docs/PLAN.md` for the full
detail and root-cause analysis behind each one):

- **Retrieval Recall@K undersells real answer quality for config/tooling questions.** The metric
  only checks `search_codebase`, which never indexes non-`.py` files (`pyproject.toml`, `tox.ini`,
  CI YAML) — the agent correctly answers these via `list_structure`+`read_file` instead, but the
  metric can't see that path. A v2 harness should score the live answer's citations directly for
  these questions, not just `search_codebase`'s output.
- **A citation-format bug undercounts nothing but also over-labels a few cases as "hallucinated."**
  The model occasionally cites a bare filename (`termui.py:12-20`) instead of the full relative
  path when a file was read earlier in the same tool sequence; `agent/grounding.py`'s exact-path
  match then fails a citation that was actually grounded. Worth a basename-tolerant matching mode
  or a stricter prompt instruction.
- **Refusal accuracy may trade off against thoroughness.** Raising the tool-call iteration budget
  (needed to stop truncating legitimate multi-file answers) coincided with lower refusal accuracy
  on 2 of 4 repos in one run — plausibly because a larger budget lets the model "try harder" on a
  genuinely unanswerable question instead of concluding early. Only 2 unanswerable questions per
  repo were tested, so this needs a larger sample before concluding it's a real effect.
- **flask's retrieval score has a persistent "one broad, frequently-relevant file wins regardless
  of sub-topic" pattern** (`app.py` outranks more specific files like `ctx.py`/`config.py` for
  several distinct questions) that a general reranking heuristic hasn't resolved.
- **No multi-turn conversation.** Each `ask`/`overview` call is independent; there's no
  session memory across questions.
- **Single API provider.** Both the answering agent and (implicitly, via Claude Code) any tooling
  around this project depend on Anthropic's API being available and funded — there's no local
  fallback model.

## Repository layout

```
src/onboard_agent/
├── config.py           # env vars: ANTHROPIC_API_KEY, ONBOARD_AGENT_MODEL, embed model
├── cache.py             # per-repo cache layout
├── ignore_patterns.py   # vendored/build dirs skipped everywhere
├── ingestion/           # sandboxed clone, repo map, ingest/load pipeline
├── chunking/            # tree-sitter AST -> Chunk models
├── indexing/            # LanceDB (dense) + bm25s (lexical) + RRF fusion + rerank
├── tools/               # single implementation of search_codebase/read_file/list_structure
├── agent/               # Tool Runner loop, overview generation, citation grounding
├── mcp_server/          # MCP server -- thin adapters over tools/ + agent/
├── cli/                 # Typer CLI: ingest / ask / overview / serve-mcp / eval
├── ui/                  # Streamlit demo UI -- thin adapter over agent/
└── evals/               # eval harness, failure taxonomy, fixture question sets
tests/
├── fixtures/tiny_repo/  # synthetic repo for fast, deterministic unit tests
├── unit/
└── integration/         # real MCP protocol, real CLI, real API calls (auto-skip w/o a key)
```
