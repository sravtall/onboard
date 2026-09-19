# OnboardAgent roadmap

## North star

**OnboardAgent should read any codebase cheaply, accurately, and robustly enough to reason
about acting on it — while staying read-only until code-writing is explicitly authorized.**

Four standing quality dimensions, in priority order. Every self-proposed phase must move at
least one without regressing the others:
1. **Accuracy** — grounded, correctly-cited answers; honest refusal when the code lacks the
   answer.
2. **Cost** — tokens/dollars per onboarding.
3. **Reach & robustness** — languages handled; never crashes on a bad repo.
4. **Usefulness** — how directly it helps a human (or another agent) understand and act.

## Done

- **v1 scaffold** (`docs/kickoff.md`): full pipeline shipped — sandboxed clone, tree-sitter
  chunking, hybrid (dense+lexical, RRF-fused) retrieval, a Tool Runner answering agent with
  citation grounding, an MCP server, a CLI, and an eval harness. Results: flask 60% recall / 97%
  groundedness / 50% refusal, requests 60% / 99% / 100% (`docs/EVALS.md`'s "v1 Baseline").
  Retrospective: proved the core loop works end to end; retrieval recall was the visible weak
  spot, deferred to Phase 2 rather than guessed at.
- **Phase 2, Phase 1 — prove the core** (`docs/PHASE2.md`): measured real onboarding-QA
  performance across 4 real repos (flask, requests, click, arrow) with ground truth from
  dispatched `explore` research, then found and fixed 5 real bugs via live instrumentation rather
  than guessing: 3 retrieval-reranking issues (subword identifier matching, a categorical
  test-file demotion, a self-named-module regression fix), a system-prompt gap for non-`.py`
  config files, and — the highest-impact fix — `MAX_TOOL_ITERATIONS` raised 8→20 after live
  evidence showed 8/33 answerable questions coming back with zero citations because Tool Runner
  was truncating mid-plan. After-fix results: arrow 100%/100%/50%, click 80%/99%/50%, flask
  67%/100%/50%, requests 89%/95%/100% (`docs/EVALS.md`'s "Phase 2" section) — no regressions,
  several large gains. New failure-taxonomy harness (`evals/taxonomy.py`) added so future
  regressions show up as a specific labeled failure mode, not just an aggregate dip.
  Retrospective: cost was never measured this whole phase — the live-answer eval runs and dev
  iteration burned through real API credits (hit the balance wall twice), with no visibility
  into where the money went. That gap is exactly this roadmap's next entry.
- **Phase 2, Phase 2 — `generate_overview`**: a structured, cited onboarding-doc capability built
  on the Anthropic SDK's native `output_format` structured-output support (not a custom "submit"
  tool). Found the same class of truncation bug as above, specific to this broader task —
  `MAX_OVERVIEW_ITERATIONS=30`, separate from Q&A's 20. New CLI command, new MCP tool (4→5
  tools), eval extension (`overview_check` + `score_overview_accuracy`). Verified live against a
  real repo: 45 citations, fully grounded.
- **Phase 2, Phase 3 — thin Streamlit UI**: one-screen demo (ingest, ask/overview, expandable
  citations backed by the real `read_file` tool, a retrieval-provenance panel) — live-verified in
  an actual browser end to end. Added `retrieved_files` to `AnswerResult`/`GenerateOverviewOutput`
  to power the provenance panel.
- **Phase 2, Phase 4 — MCP dogfood + finalize**: README overhaul (web UI usage, external MCP
  self-registration with a verified `uv run --directory` snippet, refreshed architecture diagram
  and eval summary, honest Limitations & v2 next-steps section). Fixed a real footgun hit twice
  this session: `onboard eval` no longer silently overwrites `docs/EVALS.md`'s hand-written
  analysis — now requires an explicit `--write-report` flag.

## Proposed — awaiting approval

- **Phase 3 — cost research spike** (`docs/PHASE3.md`): no cost/token instrumentation exists
  anywhere in the codebase today, despite cost being one of the four standing dimensions above.
  This phase measures a real onboarding+multi-question session's actual dollar/token cost by
  stage, surveys current cost-reduction techniques with dated, sourced pricing, and produces a
  ranked, sequenced plan in `docs/COST-RESEARCH.md` — research only, no pipeline changes beyond
  the minimal additive instrumentation needed to measure it. In progress.

## Backlog / future ideas

Carried forward from `docs/README.md`'s "Limitations & v2 next-steps" (not yet scheduled):

- Retrieval-recall metric blind spot for config/tooling questions (only checks `search_codebase`,
  which never indexes non-`.py` files) — score the live answer's citations directly instead.
- Citation-format bug: bare-filename citations (e.g. `termui.py:12-20` instead of the full
  relative path) get mislabeled as hallucinated even when grounded — basename-tolerant matching
  or a stricter prompt instruction.
- Possible refusal-accuracy trade-off from the larger tool-iteration budget — needs a bigger
  sample of unanswerable questions before concluding it's a real effect.
- flask's "one broad, frequently-relevant file wins regardless of sub-topic" retrieval pattern
  (`app.py` outranking `ctx.py`/`config.py`) — no general reranking fix found yet.
- No multi-turn conversation (each `ask`/`overview` call is independent).
- Non-Python language support, multi-repo questions, fine-tuning, cross-encoder/LLM reranking,
  a corrective re-prompt loop on failed grounding, remote MCP transport, exact commit-SHA pinning
  for evals — see `docs/PLAN.md`'s "Future work" for the full list.
