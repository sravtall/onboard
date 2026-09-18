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
   then produces a cited answer. Every citation is checked against code the agent actually
   retrieved that session before being returned.
5. **Expose** — the same read-only tools are available as an MCP server (for Claude Code,
   Claude Desktop, or any MCP client) and a CLI.

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

# Run the eval harness
uv run onboard eval
```

### MCP server

```sh
uv run onboard serve-mcp --repo https://github.com/psf/requests
# or, for a local checkout:
uv run onboard serve-mcp --local-path /path/to/checkout
```

Exposes four read-only tools: `search_codebase(query, top_k)`, `read_file(path, start_line,
end_line)`, `list_structure(path)`, and `ask_onboarding_question(question)`. See
[`.mcp.json`](.mcp.json) for a ready-to-use Claude Code configuration (set
`ONBOARD_AGENT_REPO_URL` there to point it at a specific repo).

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
              ┌──────────────┴──────────────┐
              ▼                             ▼
   agent/loop.py (Tool Runner)      mcp_server/server.py
   ask_onboarding_question()        4 tools incl. ask_onboarding_question
   + agent/grounding.py             (thin adapters, no reimplementation)
     verifies every citation
```

`src/onboard_agent/tools/` is the single implementation of the three retrieval primitives — both
the answering agent and the MCP server are thin adapters over it (see `CLAUDE.md`'s architecture
invariant). `agent/grounding.py` checks every citation in an answer against code actually
retrieved that session before returning it, surfacing `verified: bool` and any unverified
citations rather than hiding them.

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

See [`docs/EVALS.md`](docs/EVALS.md) for the full table and notes (including an honest discussion of
live-model non-determinism and a known retrieval weak spot). Summary from the latest run against
`psf/requests` and `pallets/flask`:

| Repo | Retrieval Recall@K | Citation Groundedness | Refusal Accuracy |
|---|---|---|---|
| pallets/flask | 60% | 97% | 50% |
| psf/requests | 60% | 99% | 100% |

Citation groundedness measures *every citation the agent ever produced* against code it actually
retrieved that session — it is not a proxy metric, it's the safety property the whole project
exists to guarantee. Refusal accuracy is scored on deliberately unanswerable questions (e.g.
"how does this integrate with Stripe?" against a repo with no payment code) — a correct refusal
means no fabricated citation, regardless of exact wording.

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

## Scope (v1)

**In scope:** read-only understanding of Python repos — ingestion, indexing, hybrid retrieval,
cited question-answering, an MCP server, a CLI, and an eval harness.

**Explicitly out of scope for v1** (see `docs/PLAN.md`'s "Future work" section for the full list
and why):

- Writing or proposing code changes
- Non-Python languages
- A web UI
- Multi-repo support
- Fine-tuning
- Cross-encoder/LLM-based reranking, cloud embeddings, a corrective re-prompt loop on failed
  grounding, remote MCP transport, and exact commit-SHA pinning for evals

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
├── agent/               # Tool Runner loop + citation grounding verification
├── mcp_server/          # MCP server -- thin adapters over tools/ + agent/
├── cli/                 # Typer CLI: ingest / ask / serve-mcp / eval
└── evals/               # eval harness + fixture question sets
tests/
├── fixtures/tiny_repo/  # synthetic repo for fast, deterministic unit tests
├── unit/
└── integration/         # real MCP protocol, real CLI, real API calls (auto-skip w/o a key)
```
