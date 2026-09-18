# OnboardAgent Evals

Metrics: **Retrieval Recall@K** (did the right file come back for an answerable question with a known-relevant file?), **Citation Groundedness** (fraction of citations in answerable-question answers that are confirmed against code actually retrieved that session), **Refusal Accuracy** (fraction of deliberately unanswerable questions answered without a fabricated citation). Phase 2 adds a **Failure Taxonomy** (`evals/taxonomy.py`) that labels every scored question `correct`, `retrieval_miss`, `hallucinated`, `should_refuse_but_didnt`, `incorrectly_refused`, or `needs_review`, so a regression shows up as a specific failure mode, not just a dip in an aggregate percentage.

## v1 Baseline (pallets/flask, psf/requests)

Produced by `uv run onboard eval` against `psf/requests` (commit `dae7ef63b4df6eded86637f251fc4e3a06c3b479`) and `pallets/flask` (commit `d73fa1cdcbd8b1465c151db8924ba58b1dd14e35`) — see `src/onboard_agent/evals/fixtures/`. `commit_sha` in each fixture records what these numbers were validated against; it is not an enforced checkout pin (docs/PLAN.md decision #17), so a re-run clones the current default-branch tip.

| Repo | Questions (answerable / unanswerable) | Retrieval Recall@K | Citation Groundedness | Refusal Accuracy |
|---|---|---|---|---|
| pallets/flask | 5 / 2 | 60% | 97% | 50% |
| psf/requests | 5 / 2 | 60% | 99% | 100% |

### Notes on these numbers

- **Citation groundedness and refusal accuracy are not always 100%, and that's the harness working correctly, not a bug.** The answering agent calls a live, non-deterministic model — this run happened to fabricate one ungrounded citation on one of flask's two unanswerable questions, and `agent/grounding.py` caught it (that's exactly what dropped refusal accuracy to 50% here rather than the harness silently reporting a clean pass). A follow-up ad-hoc re-ask of the same two flask questions came back fully grounded on both, confirming this was call-to-call variance rather than a systematic gap. Re-running `onboard eval` will not reproduce identical numbers every time; treat single-digit-percent groundedness dips as expected model variance, not regressions, unless they persist across repeated runs.
- **Retrieval Recall@K's consistent weak spot is "what's the test setup" / "how does the CLI entry point work" style questions** — both repos missed `tests/conftest.py` for the test-setup question (surfacing other test files instead), and flask missed `src/flask/cli.py` for the `flask run` question (surfacing `src/flask/app.py` instead, which is topically related but not the file the fixture names). Indexing text was updated to include each chunk's `file_path` (docs/PLAN.md decision #18) on the theory that filename tokens like "conftest" or "cli" would help; it did not move Recall@K on these specific questions in this run. Left as a known v1 limitation rather than over-fit to two fixture questions — see "Future work" in `docs/PLAN.md`. **Phase 2 revisits this below.**
- Every citation in every answerable-question answer across both repos that *did* pass grounding was independently confirmed against real file/line content actually retrieved that session — groundedness failures are exclusively the one flagged case above, not a broader pattern of unverifiable citations slipping through.

### Generalization beyond the eval fixtures

`psf/requests` and `pallets/flask` had their question sets designed in advance, so a smoke test against a repo with zero advance question design is a stronger generalization signal. Asked `onboard ask "What is the main purpose of this library and what does it help Python developers do?" --repo https://github.com/benjaminp/six` (a repo never referenced anywhere else in this project) produced a fully-grounded, multi-citation answer on the first try — see docs/PLAN.md decision #19 for a real bug this same smoke test caught (a Windows console encoding crash, unrelated to retrieval/grounding, fixed in `cli/_console_encoding.py`).

## Phase 2: Failure Taxonomy & Fix

Two new repos joined the eval corpus — `pallets/click` (a CLI framework, chosen because Typer, which wraps it, powers this project's own CLI) and `arrow-py/arrow` (a small, clean date/time library, chosen for contrast against flask/requests/click's larger surface area) — and `flask.yaml`/`requests.yaml` were both extended with 4 new ground-truth questions each. Ground truth for all four repos (question + real relevant file(s), verified by reading the code) was researched via dispatched `explore` subagent sessions, not guessed. Final corpus:

| Repo | Questions (answerable / unanswerable) |
|---|---|
| arrow-py/arrow | 10 / 2 |
| pallets/click | 10 / 2 |
| pallets/flask | 9 / 2 |
| psf/requests | 9 / 2 |

### Baseline (pre-Phase-2 code, full Phase 2 question set)

Measured with a clean `git stash` of every Phase 2 code change (retrieval + prompt), run against the fixtures above, `--retrieval-only` (free, no live model calls needed to measure this metric):

| Repo | Retrieval Recall@K |
|---|---|
| arrow-py/arrow | 100% |
| pallets/click | 70% |
| pallets/flask | 67% |
| psf/requests | 78% |

### Fixes applied

Real error analysis, not guessing — each fix below was root-caused from an actual observed miss, and each was verified to move the specific metric it targeted before being kept.

1. **Subword-tokenized identifier/filename matching** (`indexing/hybrid.py`) — flask's `flask run` question missed `cli.py`, surfacing `app.py` instead, because the identifier-match bonus split on nothing but exact word boundaries: a query containing "run" never matched the symbol `run_command` (the underscore was treated as part of one token). Splitting identifiers on `.`/`_` as well as whitespace fixed it (docs/PLAN.md decision #21).
2. **Categorical test-file demotion in rerank** — baseline error analysis on the *new* `click`/`arrow` fixtures showed real source files losing to test files whose own test-function name happened to echo the query's identifier (`test_argument_metavar_...` outranking `src/click/core.py` for an "argument" question). A small penalty (0.05) wasn't enough to overcome the identifier-match bonus a test's own name earns; a deliberately large, categorical penalty (0.5, exempted when the query is itself about testing/setup) was needed (docs/PLAN.md decision #21).
3. **Self-named-module correction** — the filename-stem bonus from fix 1, while it didn't cause fix 1's own motivating case, caused a **measured regression** on `arrow-py/arrow` (Recall@K 100% → 80%): `arrow/arrow.py`'s stem ("arrow") matches the package's own name, which appears in nearly every onboarding question about the library, so every chunk in that one file won the bonus regardless of which sub-topic was actually asked about. Suppressing the bonus when a filename repeats its own parent directory fixed it without touching the `click`/`requests` gains or the original flask fix (docs/PLAN.md decision #22).
4. **System-prompt nudge for config/tooling questions** — `search_codebase` only indexes `.py` files, so it can never surface `pyproject.toml`/`tox.ini`/CI YAML no matter how the rerank is tuned; "what's the test setup" questions need those files. Added an instruction telling the agent to use `list_structure`+`read_file` directly for setup/config/CI questions. Verified live: the agent now correctly cites `pyproject.toml`, `tox.ini`, `.coveragerc`, and CI workflow files for that question — even though the Retrieval Recall@K *metric* (which only checks `search_codebase`) still shows a miss on it, since this fix routes through a different tool entirely (docs/PLAN.md decision #22).
5. **`MAX_TOOL_ITERATIONS` raised 8 → 20** (`agent/loop.py`) — by far the highest-impact fix, found only because the *live-answer* taxonomy eval (not just retrieval) was run. See its own section below.

### After fixes 1-4 (retrieval only)

| Repo | Baseline Recall@K | After Recall@K |
|---|---|---|
| arrow-py/arrow | 100% | 100% (no regression, after fix 3 corrected fix 1's side effect) |
| pallets/click | 70% | 80% |
| pallets/flask | 67% | 67% (unchanged — its remaining misses are a distinct issue, see below) |
| psf/requests | 78% | 89% |

No repo regressed; two improved substantially; flask's retrieval score is flat but its live-answer quality improved dramatically once fix 5 landed (below) — the config-file question it "misses" on this metric is answered correctly in practice via fix 4's `list_structure`/`read_file` path.

### The `MAX_TOOL_ITERATIONS` bug

Running the full live-answer taxonomy eval (fixes 1-4 only, cap still at 8) surfaced something the retrieval-only metric couldn't: **8 of 33 answerable questions across flask/requests/click came back with zero citations**, all labeled `incorrectly_refused`. Instrumenting one live call directly (flask's session-cookie question) showed the actual cause: the model was still mid-plan — issuing another `read_file` call to check `sansio/app.py`'s `default_config` — when the 8th tool-call round hit `max_iterations`. Tool Runner stopped there, and the "final message" handed back was a stray one-sentence tool-call preamble, not a synthesized answer. This is not a real refusal; it's a truncation artifact that the taxonomy's `incorrectly_refused` label caught precisely because it checks for *empty citations on an answerable question*, not just whether the model said "I don't know."

Raising the cap to 20 and re-running confirmed the fix directly: that same flask question went from 0 citations to 17, all grounded.

| Repo | `incorrectly_refused` before | `incorrectly_refused` after |
|---|---|---|
| pallets/flask | 4 / 9 | 0 / 9 |
| psf/requests | 3 / 9 | 0 / 9 |
| pallets/click | 1 / 10 | 0 / 10 |
| arrow-py/arrow | 0 / 10 | 0 / 10 |

### After all fixes (full corpus, live answers)

| Repo | Recall@K | Citation Groundedness | Refusal Accuracy | Taxonomy (non-zero labels) |
|---|---|---|---|---|
| arrow-py/arrow | 100% | 100% | 50% | `should_refuse_but_didnt`: 1/2 |
| pallets/click | 80% | 99% | 50% | `hallucinated`: 1/10, `should_refuse_but_didnt`: 1/2 |
| pallets/flask | 67% | 100% | 50% | `should_refuse_but_didnt`: 1/2 |
| psf/requests | 89% | 95% | 100% | `hallucinated`: 2/9 |

### Known remaining weak spots (honestly reported, not fixed)

- **Refusal accuracy dropped on 2 of 4 repos when the iteration cap was raised** (click and flask both went 100% → 50% on their 2 unanswerable questions between the fixes-1-4 run and the final run). With only 2 unanswerable questions per repo this could be ordinary live-model call-to-call variance (already documented as expected in the v1 notes above) — but both repos moved in the *same* direction in the same run, which is at least suggestive of a real mechanism: a larger iteration budget may let the model "try harder" on a genuinely unanswerable question instead of concluding early that nothing relevant exists, eventually producing a plausible-sounding but ungrounded citation instead of an honest refusal. Flagged as a hypothesis for v2, not a proven regression — n=2 per repo is too thin to be conclusive from a single run.
- **flask's Retrieval Recall@K (67%) has two remaining, distinct root causes**, neither fixed by the rerank changes above: (1) the context-stack and app-config questions keep surfacing `app.py`/`sansio/app.py` instead of the more specific `ctx.py`/`globals.py`/`config.py` — likely the same "one broad, frequently-relevant file wins regardless of sub-topic" pattern as the arrow regression, but harder to fix generically since `app.py` genuinely is relevant to many flask questions (unlike arrow's self-named-module case); (2) `tests/conftest.py` itself still doesn't outrank other flask test files for the test-setup question, even though the categorical test-file penalty correctly exempts it. Both are now correctly answered anyway in practice by the live agent using `list_structure`/`read_file` directly — see fix 4 — so this is a metric-methodology gap (Recall@K only checks `search_codebase`) more than a live-answer quality gap.
- **A citation-format bug**: click's and requests' `hallucinated` cases are not fabricated content — inspecting the raw citations shows the model sometimes emits a bare filename (`termui.py:121-127`) instead of the full relative path (`src/click/termui.py:121-127`) when a file was read earlier in the same tool-call sequence, which `agent/grounding.py`'s exact-path containment check correctly fails to match against the retrieved span. This under-counts real hallucinations by conflating them with a citation-formatting inconsistency. Worth a v2 fix (either normalize citations to basename-tolerant matching in `grounding.py`, or tighten the system prompt to always cite the full path `read_file`/`search_codebase` returned) rather than a Phase 2 scope item.

**Exit criteria met**: before/after improvement demonstrated on multiple failure modes (`incorrectly_refused`, `retrieval_miss` via Recall@K) across all 4 real repos, with root causes verified via direct instrumentation rather than assumed.
