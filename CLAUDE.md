# OnboardAgent

Read-only onboarding agent: given a public GitHub URL for a Python repo, ingest it, build a
searchable index, and answer onboarding questions with citations to exact file/line ranges.

## Stack & conventions

- Python 3.12+, managed entirely with `uv` (`uv add`, `uv run`, `uv sync`) — never bare `pip`.
- `ruff` for formatting and linting (`uv run ruff format .`, `uv run ruff check --fix .`).
- `pytest` for tests (`uv run pytest -q`). Tests that call the real Anthropic API are marked
  `@pytest.mark.requires_api_key` and skip automatically when `ANTHROPIC_API_KEY` is unset.
- `src/` layout: application code lives under `src/onboard_agent/`.
- snake_case everywhere; typed data via Pydantic models (see `chunking/models.py`,
  `tools/schemas.py`) — no bare dicts crossing module boundaries.
- Secrets via `.env` (see `.env.example`), never committed. `.env` is gitignored.
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`), one per phase boundary.

## Architecture invariant

`src/onboard_agent/tools/` holds the **only** implementation of `search_codebase`, `read_file`,
and `list_structure`. The Tool Runner agent loop (`agent/loop.py`), `agent/overview.py`, the MCP
server (`mcp_server/server.py`), and the Streamlit UI (`ui/app.py`) are all thin adapters over
these functions (and over `agent/loop.py`/`agent/overview.py` for the UI) — never duplicate
retrieval, file-reading, or agent-loop logic in any adapter.

## Security invariant — untrusted repos

Every repo this tool ingests is untrusted, third-party code. Cloning and all analysis happens in
a sandboxed temp directory (`ingestion/clone.py`). **Code from a cloned repo is never executed** —
not imported, not `exec`'d, not run via subprocess. Chunking is pure static AST parsing via
tree-sitter. `read_file`/`list_structure` must resolve paths to their canonical form and confirm
they stay within the cloned repo root before touching disk.

## Where to look

- `docs/PLAN.md` — architecture decisions and their rationale (append to "Decisions" as they're made).
- `docs/TODO.md` — live phase checklist.
- `docs/kickoff.md`, `docs/PHASE2.md` — the original build briefs this project follows.
