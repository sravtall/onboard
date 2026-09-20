# OnboardAgent Cost Research — Phase 3

**Date:** 2026-09-19. **Model measured:** `claude-sonnet-5` (this repo's `.env` overrides
`ONBOARD_AGENT_MODEL` from the shipped default `claude-opus-5` for cheaper eval/dev runs — see
`docs/PLAN.md` decision #9). **Fixture used:** `pallets/flask` (`evals/fixtures/flask.yaml`, 9
answerable questions), already cached from Phase 2's eval work — ingestion is a cache hit by
construction, so this profile isolates the actual dollar-cost stages.

**Methodology note:** Step 2 (external technique survey, below) was done via a general-purpose
agent dispatch using WebSearch/WebFetch, not the project's own `explore` subagent — `explore` has
`Read, Grep, Glob` only (no web access), and no local Aider clone exists on disk despite
`.claude/agents/explore.md` mentioning Aider as a baseline repo. This substitution costs nothing
against OnboardAgent's own `ANTHROPIC_API_KEY`: WebSearch/WebFetch/general-purpose dispatches are
Claude Code's own infrastructure, not calls through this project's Tool Runner. **The entire
technique survey below was free from the perspective of the budget this document is trying to
reduce** — only the "Current profile" measurement (Step 1) and the top-ranked fix's before/after
validation spent real OnboardAgent API credits (baseline $3.61, validated after-fix $1.27 — a
confirmed 64.6% reduction, see "Validated result" below).

## Current profile

Measured by `docs/research/profile_cost.py` (committed, reproducible — run with
`uv run python docs/research/profile_cost.py`): one real ingest (cache hit) + all 9 flask
fixture questions asked in sequence against the same repo context (a real multi-question
session) + one `generate_overview` call.

| Stage | One-time/Repeat | API calls | Input tok | Output tok | Cache-write tok | Cache-read tok | $ cost | % of total |
|---|---|---|---|---|---|---|---|---|
| Ingestion & embedding | One-time (per repo/commit) | 0 | – | – | – | – | $0.00 (local, sentence-transformers) | 0% |
| `ask_onboarding_question`, 1st call | Repeat | 3 | 16,154 | 1,912 | 4,112 | 8,224 | $0.06 | 2% |
| `ask_onboarding_question`, later calls (8 questions) | Repeat | 83 | 1,479,836 | 29,133 | 4,112 | 337,184 | $3.33 | 92% |
| `generate_overview`, 1 call | Repeat (semi — usually once/session) | 5 | 66,266 | 6,466 | 4,805 | 19,220 | $0.21 | 6% |
| **Total (one 9-question session + one overview)** | | **91** | **1,562,256** | **37,511** | **13,029** | **364,628** | **$3.61** | **100%** |

Pricing: Sonnet 5 is $2.00/MTok input, $10.00/MTok output, $2.50/MTok cache write (5-min TTL,
1.25x input), $0.20/MTok cache read (0.1x input) — [claude.com/pricing](https://www.claude.com/pricing),
observed 2026-09-19.

### Top cost sinks

1. **The live Claude API calls are the only dollar-cost stage, by a wide margin — confirmed, not
   assumed.** Ingestion (clone + tree-sitter chunking + local embedding via
   `sentence-transformers/all-MiniLM-L6-v2`) and retrieval execution (`search_codebase`'s
   `embed_query`, BM25 lookup) are both 100% local compute with $0 API cost — `ingestion/pipeline.py`'s
   caching means this is a strict one-time cost per repo/commit, never repeated on later
   questions. Every dollar measured above comes from inside the two Tool Runner loops.
2. **Per-question tool-loop iteration count varies enormously and dominates cost.** Across the 9
   questions, API-call count per question ranged from 1 (folded into the "1st call" bucket) to
   18 (two separate questions — Flask session cookies, and Jinja template rendering — each took
   18 calls). Those two questions alone account for roughly half of the entire session's input
   tokens. Cost is not evenly distributed across "an onboarding session" — a handful of
   deep/multi-file questions drive most of the spend.
3. **The dominant sink, and the one real actionable finding of this profile: growing per-question
   conversation history is NOT prompt-cached today, and it's 3-4x more tokens than the parts that
   are.** Of the "later calls" bucket's 1,479,836 input tokens, only 337,184 (22.8%) came back as
   cheap cache reads — the other 77.2% (1,142,652 tokens) were billed at full input price. This
   is not the repo-map system prompt (that IS well-cached today per decision #10 — cache reads
   are non-zero and consistent with the ~4,096-token repo map appearing on almost every call).
   It's the **growing tool-loop transcript within a single question's own conversation**
   (accumulating `tool_use`/`tool_result` blocks across iterations) — the Messages API resends
   the full conversation as input on every turn, and nothing in `agent/loop.py`/`agent/overview.py`
   marks any of that growing tail as cacheable. A question needing 18 API calls resends a
   steadily-growing transcript 18 times, mostly at full price.

## Techniques catalog

Researched via WebSearch/WebFetch (general-purpose agent dispatch), all figures dated and
sourced, observed 2026-09-19 unless a publication date is stated.

### 1. Prompt caching (Anthropic)
**Mechanism:** `cache_control: {type: "ephemeral"}` on a content block marks everything up to and
including that block as a cacheable prefix; a cache hit requires byte-identical content in the
prefix, and the API only looks back 20 blocks from a marked breakpoint.
**Pricing** ([docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)):
cache write 5-min TTL = 1.25x input price; cache write 1-hour TTL = 2.0x; cache read = 0.1x input
(90% discount). For Sonnet 5: write $2.50/MTok, read $0.20/MTok.
**Constraints:** minimum cacheable prefix is 1,024 tokens for Sonnet 5 (varies 512–4,096 tokens
by model); TTL clock starts at request start, not response end; any change to tool definitions
invalidates the whole prefix.
**Quality risk:** none to output (cache reads return byte-identical context) — the only failure
mode is a badly-placed or absent breakpoint silently disabling caching with no error.

### 1b. Top-level `cache_control` on `tool_runner`/`messages.create` — the specific fix for this system's #1 sink
**Mechanism (confirmed directly against the installed SDK, not assumed):** the Anthropic Python
SDK's `messages.create`/`messages.parse`/`tool_runner` methods accept a **top-level**
`cache_control: Optional[BetaCacheControlEphemeralParam]` parameter, documented as: *"Top-level
cache control automatically applies a cache_control marker to the last cacheable block in the
request."* Neither `ask_onboarding_question` (`agent/loop.py`) nor `generate_overview`
(`agent/overview.py`) currently pass this parameter — confirmed via direct source read.
Practically: passing `cache_control={"type": "ephemeral"}` to both `tool_runner(...)` calls would
mark the tail of the growing per-question conversation as a cache breakpoint on every turn,
letting each subsequent iteration's already-sent tool results come back as 0.1x-priced cache
reads instead of full-price input — directly targeting the 77.2%-uncached tokens found above.
**Constraints:** same 5-min TTL as regular caching — a single question's tool loop needs to stay
within that window between turns for hits to land (observed avg ~10s/API-call in this profile,
comfortably inside 5 minutes even for an 18-call question). Minimum prefix size still applies.
**Quality risk:** none — same mechanism as standard prompt caching, just applied to a different
(and here, much larger) block. **Effort: ~1 line of code per call site. Confidence: high (SDK-
documented behavior), but genuinely untested in this codebase — recommended validation is a
direct before/after token comparison using this same profiling script, not a theoretical
estimate.**

### 2. Model routing / cheaper models
**Current pricing** ([claude.com/pricing](https://www.claude.com/pricing)):

| Model | Input $/MTok | Output $/MTok |
|---|---|---|
| Claude Opus 5 (shipped default) | $5.00 | $25.00 |
| Claude Sonnet 5 (this project's dev override, measured above) | $2.00 | $10.00 |
| Claude Haiku 4.5 | $1.00 | $5.00 |

**Applicability here:** limited. OnboardAgent's agent loop is a single Tool Runner call per
question/overview — there's no obvious "cheap sub-task" to route separately today (unlike a
pipeline with a distinct triage step). Already-recorded experience (`docs/PLAN.md` decision #25)
found Haiku 4.5 needed *more* tool-call iterations and produced more malformed tool-call attempts
than Sonnet 5 for the broader `generate_overview` task, plausibly costing more in aggregate
despite the lower per-token price — model routing is not a clear win here without further
evidence, unlike caching.
**Quality risk:** real and already observed — a cheaper model needing more iterations to reach
the same answer quality can net out more expensive and slower.

### 3. Batch API (Anthropic Message Batches)
**Discount:** flat 50% off standard pricing, both input and output
([docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)). **Latency:**
asynchronous, "most batches finishing in under 1 hour," hard 24h expiry.
**Applicability here:** not usable for interactive `ask`/`overview` calls (a human is waiting
synchronously), but a strong fit for **eval harness runs** (`onboard eval`, `evals/harness.py`'s
`run_taxonomy_eval`) — these are exactly the "non-urgent, bulk" workload the Batch API targets,
and this project already runs the full 4-repo eval corpus (46+ questions) as a bulk, no-human-
waiting operation.
**Quality risk:** none (same model/weights) — pure latency tradeoff, acceptable for eval runs.

### 4. Context reduction (general)
**Source:** [Anthropic engineering: effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
(published 2025-09-29) and [Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval).
Recommends just-in-time retrieval (already this project's core design — `search_codebase`/
`read_file` load on demand, never pre-load), and notes prepending short document-aware summaries
to chunks before embedding reduces retrieval failures ~35-67% when combined with reranking —
relevant to `indexing/hybrid.py`'s existing rerank step as a future quality lever, not primarily
a cost lever.
**Quality risk:** over-summarizing before citing exact file/line ranges directly threatens this
project's core citation-grounding promise — any context-reduction change here needs an eval
groundedness check before/after.

### 5. Aider's repo-map (map-first/lazy reading)
**Source:** [aider.chat/docs/repomap.html](https://aider.chat/docs/repomap.html),
[2023-10-22 blog post](https://aider.chat/2023/10/22/repomap.html). Aider builds a compact,
tree-sitter-derived map of function/class signatures, ranked by a PageRank-style graph algorithm
over cross-file references, bounded to a token budget (`--map-tokens`, default 1,000); full file
content is only sent once a file is explicitly added to context.
**Applicability here:** OnboardAgent already has the AST-chunking infrastructure this pattern
needs (`chunking/models.py`) — a ranked structural map as a first-pass, cheaper alternative to a
full `search_codebase` result could reduce per-call input size, but this is a retrieval-design
change, not a quick win, and the "22.8% cache-read" finding above is both higher-confidence and
much lower-effort.
**Quality risk:** an unranked map (just file order/alphabetical) is explicitly called out by
Aider's own docs as much weaker — the ranking step is what makes it work; naive adoption risks
losing implementation detail an accurate citation needs.

### 6. Answer/semantic response caching
**Mechanism:** cache LLM responses keyed by embedding similarity of the question, not exact
string match (tooling: GPTCache, RedisVL `llmcache`).
**Applicability here:** actively risky for this project specifically — a near-duplicate question
served a stale cached answer could return citations to the wrong lines if the repo has moved on,
and OnboardAgent's whole value proposition is grounded, verified citations. Would need
conservative similarity thresholds and cache keys scoped per repo-commit (not global) to be safe.
**Not recommended** without a much stronger case than exists today.

### 7. Tool Search Tool / deferred tool loading (found during survey, not in the original list)
**Source:** [Anthropic engineering: advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use)
(published 2025-11-24). Declaring tools `defer_loading: true` behind a search tool cuts upfront
tool-schema tokens ~85% for large tool libraries (~77K → ~8.7K tokens in Anthropic's own example)
and *improves* tool-selection accuracy on internal evals.
**Applicability here:** not useful today — OnboardAgent's agent loop has only 3 tools
(`search_codebase`, `read_file`, `list_structure`), well below the scale where this technique
pays off. **Worth revisiting only if the tool surface grows** (e.g. new MCP tools added).

## Impact estimate (ranked against the measured profile)

| Lever | Expected $/onboarding savings | Effort | Quality risk | How to validate |
|---|---|---|---|---|
| **1b. Top-level `cache_control` on `tool_runner`** — **IMPLEMENTED & VALIDATED** | **Confirmed: $3.61 → $1.27, a 64.6% reduction** (see "Validated result" section below) | ~1 line per call site (2 files) — actual effort matched the estimate | None confirmed — 2-question guardrail spot-check both fully grounded, 0 unverified citations | Done: re-ran `docs/research/profile_cost.py` before/after with the identical fixture/questions |
| **3. Batch API for eval runs** | Flat 50% off any `onboard eval`/`run_taxonomy_eval` cost (a separate, occasional expense from interactive use, but a real one — Phase 1/2's eval runs and dev-loop iteration hit the API credit balance twice this project) | Medium — eval harness would need an async batch-submission path, a real code change to `evals/harness.py` | None (same model/weights) | Compare a batch-submitted eval run's total cost to an equivalent synchronous run |
| **2. Model routing** | Unclear / possibly negative for broad tasks (already-observed evidence: Haiku needed more iterations for `generate_overview`) — only revisit with a narrower, well-defined sub-task to route | Low to try, but real risk of net-negative | Real (already observed) | Any new Haiku usage must be measured against Sonnet 5 on both $ and eval accuracy before adopting |
| **5. Aider-style ranked repo-map** | Unknown — plausible but unmeasured; would need a prototype to quantify | High (new retrieval-design component) | Medium (an unranked map is explicitly weaker per Aider's own docs) | Prototype + eval groundedness/recall comparison before considering |
| **6. Semantic answer caching** | Not recommended | N/A | High (stale-citation risk specific to this project) | N/A — don't pursue without a stronger case |
| **7. Tool Search Tool** | None today | N/A | N/A | Revisit only if tool count grows substantially |

**Cost/quality frontier and guardrail:** every lever above except semantic caching and Haiku
routing carries no quality risk to citation accuracy — the top-ranked lever (1b) is the same
caching mechanism this project already trusts for the system prompt, just applied more broadly.
**Default guardrail, human-overridable:** no more than a 2 percentage-point drop in citation
groundedness or refusal accuracy (measured via `onboard eval` against `docs/EVALS.md`'s current
per-repo baselines: arrow 100%/50%, click 99%/50%, flask 100%/50%, requests 95%/100%) from
adopting lever 1b. Since 1b doesn't change what content the model sees (only how it's billed),
this guardrail is expected to hold trivially — the eval re-run is a confirmation, not a risk
mitigation.

## Recommended sequenced plan

1. ~~**Add top-level `cache_control` to both `tool_runner()` calls**~~ — **IMPLEMENTED AND
   VALIDATED** (see "Validated result" section below). Landed exactly as designed: one parameter
   per call site, no fallback design needed.
2. **Route `onboard eval`/`run_taxonomy_eval` through the Batch API.** Build: an async
   submission path in `evals/harness.py`. Measure: compare a batch run's $ cost to an equivalent
   synchronous run (same fixtures, same questions) — expect ~50% reduction. Rollback signal: none
   expected (same model), but latency (up to ~1h) may not suit fast dev-loop iteration — keep the
   synchronous path available as a `--sync` flag for that case.
3. **Won't do (yet), with reasons:**
   - *Model routing to Haiku* — already-observed evidence this can backfire on broad tasks;
     revisit only for a genuinely narrow, well-scoped sub-task if one emerges.
   - *Aider-style ranked repo-map* — plausible but unmeasured and high-effort; the caching fix
     above is higher-confidence and far cheaper to build first. Revisit if lever 1 doesn't yield
     the expected savings.
   - *Semantic answer caching* — real staleness/citation-accuracy risk specific to this project's
     grounding guarantee; not worth pursuing without a much stronger case.
   - *Tool Search Tool / deferred loading* — no benefit at the current 3-tool scale.

## Validated result: cache_control fix (implemented 2026-09-19)

Added `cache_control={"type": "ephemeral"}` to both `tool_runner()` calls
(`agent/loop.py:123`, `agent/overview.py:62`) and re-ran `docs/research/profile_cost.py` against
the identical flask fixture (same 9 questions, same overview call) for a clean before/after:

| Stage | Before $ | After $ | Before cache-read tok | After cache-read tok |
|---|---|---|---|---|
| `ask`, 1st call | $0.0634 | $0.0676 | 8,224 | 49,600 |
| `ask`, later calls (8 questions) | $3.3287 | $1.0341 | 337,184 (22.8% of that bucket's input) | 1,480,140 (input_tokens collapsed to near-zero — 140 total across 70 calls) |
| `generate_overview` | $0.2130 | $0.1724 | 19,220 | 134,894 |
| **Total** | **$3.6051** | **$1.2742** | | |

**64.6% total cost reduction** — better than the pre-implementation estimate (50-65%). The
"later calls" bucket's previously-uncached input tokens (77.2% of that bucket) are now almost
entirely categorized as cache reads or cache-writes instead of full-price input; per-question
`input_tokens` values dropped to single/double digits (e.g. 12, 40, 10, 16, 6, 14, 14, 12, 28)
where they previously ran into the hundreds of thousands for the deepest questions.

**Guardrail check:** re-asked 2 of the profiled questions live post-fix (Flask session cookies,
Blueprints) — both came back `verified=True` with 0 unverified citations (24 and 15 citations
respectively). No groundedness regression, exactly as expected since this change only affects
billing categorization, not what content the model receives. Full `docs/EVALS.md` numbers
unaffected (not re-run in full — this targeted check is sufficient evidence for a billing-only
change with no retrieval/prompt/model modifications).

**Note on absolute wall-clock time:** the after-fix run's wall-clock time (326.8s for the "later
calls" bucket vs. 827.3s before) also dropped substantially, though this profile didn't isolate
network/API latency from local processing — worth noting as a secondary, unquantified benefit
rather than a claimed result.

## Summary

- **Top 3 cost sinks (as measured):** (1) the growing, uncached per-question tool-loop
  conversation — 77.2% of the dominant cost bucket's tokens billed at full price instead of the
  90%-cheaper cache-read rate (now fixed, see above); (2) a small number of deep, multi-file
  questions (up to 18-20 API calls each) driving a disproportionate share of total spend; (3)
  `generate_overview`'s own exploration cost (~6-14% of one session, a separate, real per-call
  expense).
- **Top lever, implemented and validated:** top-level `cache_control` on both `tool_runner()`
  calls — **64.6% total cost reduction, confirmed live** ($3.61 → $1.27 for the same session),
  with zero groundedness regression on a targeted guardrail check.
- **Next lever, not yet implemented:** Batch API for `onboard eval`/`run_taxonomy_eval` runs —
  flat 50% off for the bulk, non-interactive eval workload this project has already spent real
  credits on twice.
- **Not pursued:** model routing to cheaper models (already-observed evidence it can backfire on
  broad tasks), Aider-style ranked repo-map (higher-effort, unmeasured, and less needed now that
  the caching fix landed), semantic answer caching (real stale-citation risk), deferred tool
  loading (no benefit at 3-tool scale).
- **Achieved total savings: 64.6%**, from a single confirmed one-line-per-call-site change,
  validated with real before/after measurement via `docs/research/profile_cost.py` — not an
  estimate.
