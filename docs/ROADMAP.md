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
- **Phase 3 — cost research spike** (`docs/PHASE3.md` → `docs/COST-RESEARCH.md`): measured a
  real 9-question flask session + 1 overview call end to end via new additive instrumentation
  (`UsageTotals`/`accumulate_usage`, `docs/PLAN.md` decision #29) — $3.61 total, 91 live API
  calls, with 92% of cost concentrated in one bucket. Root-caused that bucket: 77.2% of its
  tokens were billed at full price because the growing per-question tool-loop conversation is
  never marked cacheable, only the static system/repo-map block is. Surveyed 7 current
  cost-reduction techniques (dated, sourced pricing) via a general-purpose agent dispatch
  (WebSearch/WebFetch — `explore` has no web access and no local Aider clone exists). Found a
  high-confidence, ~1-line fix directly from the measured data plus a live SDK source check
  (not assumed): a top-level `cache_control` parameter on `tool_runner()` that neither
  `ask_onboarding_question` nor `generate_overview` currently passes. Retrospective: cost is now
  visible for the first time — previously the weakest-instrumented of the four standing
  dimensions, now has both a real number and a specific, ranked fix ready to build. No regression
  risk introduced (purely additive instrumentation, confirmed via the full non-API test suite
  staying green at 75 passed). Debt/risk: the recommended fix (lever 1b) is SDK-documented but
  genuinely untested in this codebase — its actual effect size is an estimate pending
  implementation, not yet a confirmed result.

## Proposed — awaiting approval

- **Phase 4 — implement the top-ranked cost fix** (`docs/COST-RESEARCH.md`'s "Recommended
  sequenced plan" item 1): add a top-level `cache_control={"type": "ephemeral"}` parameter to
  both `tool_runner()` calls in `agent/loop.py` and `agent/overview.py`. Rationale: highest
  impact (targets a measured 92%-of-cost bucket) at lowest effort/risk (one parameter per call
  site, same caching mechanism this codebase already trusts elsewhere) of everything surveyed —
  clearly beats the alternatives (model routing has already-observed evidence it can backfire;
  an Aider-style repo-map is high-effort and unmeasured; semantic caching carries real
  stale-citation risk). Exit criteria: re-run `docs/research/profile_cost.py` against the same
  flask fixture before/after and show a material increase in `cache_read_input_tokens` share of
  the "later calls" bucket and a corresponding drop in total $ cost. Guardrail: no more than a 2
  percentage-point drop in citation groundedness/refusal accuracy vs. `docs/EVALS.md`'s current
  per-repo baselines (arrow 100%/50%, click 99%/50%, flask 100%/50%, requests 95%/100%) — expected
  to hold trivially since this changes billing, not model input content, but confirmed via
  `onboard eval` rather than assumed. Excluded from this phase: the Batch API lever for eval runs
  (item 2 of the recommended sequence) — sequenced second, after this higher-confidence fix lands
  and is measured.

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
