# OnboardAgent — Phase 3.0 research spike: how to lower cost

> **How to use.** Drop this in the repo as `PHASE3-RESEARCH.md` and run it **before**
> `PHASE3.md`. Send: *"Read PHASE3-RESEARCH.md and execute it. Follow the operating protocol
> exactly."* Its output (a ranked, evidence-backed plan in `COST-RESEARCH.md`) then drives
> Phase 3's build — update `PHASE3.md`'s Phase 1 to match the findings before building.

---

## 1. Mission

Before optimizing anything, **find out where the money actually goes and what will actually
move it.** Produce a prioritized, evidence-backed cost-reduction plan grounded in (a) a real
profile of *this* system and (b) current best practices and pricing. This is a research
spike: the deliverable is a decision document, **not** production changes. Resist the urge to
start refactoring — investigate, rank, recommend, then hand off to the build.

## 2. Operating protocol

- **Re-orient first:** read `PLAN.md`, `EVALS.md`, `COST.md` (if present), and the code.
- **Measure before you theorize.** The profile of the real system is the most important
  input — generic cost advice is useless without knowing this system's bottleneck.
- **Verify current facts.** Pricing, prompt-caching discounts, and batch-API discounts change
  and are exactly the numbers you're reasoning about — fetch them from provider docs, don't
  use remembered figures. Date every figure you cite.
- **Delegate** research reading to the `explore` subagent (baseline tools, docs).
- **Only stop if truly blocked;** otherwise choose a sensible default, record it, continue.
- This phase produces documents and small throwaway measurement scripts only — no changes to
  production code paths. Commit the research artifacts, not refactors.

## 3. Step 1 — profile the real system (empirical, do this first)

You cannot rank fixes without knowing the bottleneck. Instrument and measure.

1. Add temporary, fine-grained cost/token tracing (or extend existing tracing) and run a
   **full onboarding of a representative repo** plus a **multi-question session** on it.
2. Break the cost down by stage and by call: ingestion/embedding, index build, per retrieval,
   each agent/LLM step, overview generation. Capture tokens (input/output separately — output
   is priced higher) and dollars per stage.
3. Identify the **top 3–4 cost sinks** and quantify each as a share of total. Distinguish
   *one-time* costs (initial embedding) from *repeat* costs (every question) — they call for
   different fixes.
4. Record this as the "Current profile" section of `COST-RESEARCH.md`, with a simple
   breakdown table. This is the ground truth every recommendation is measured against.

**Checkpoint:** a measured cost breakdown of a real onboarding, top sinks quantified.

## 4. Step 2 — survey cost-reduction techniques (external research)

For each candidate lever, research how it works, its *current* real-world savings, its
constraints, and its quality risk. Use provider docs and reputable practitioner sources; cite
and date everything. Candidates to investigate (add any you find):

- **Index/embedding persistence & incremental re-embedding** — embed once, reuse; re-embed
  only changed files. (Targets one-time cost paid repeatedly.)
- **Prompt caching** — caching a stable prefix (system prompt + repo map) across calls; find
  the *current* discount and the constraints (min prefix size, TTL, what invalidates it).
- **Model routing / cheaper models** — cheap or open-weight models for mechanical steps,
  frontier only for synthesis; get current per-token prices across a few tiers, including at
  least one open-weight option.
- **Batch API** — current discount for non-urgent work (e.g., bulk embedding/eval); latency
  tradeoff.
- **Context reduction** — tighter retrieval (rerank, small top-k), summaries over raw code,
  compression/compaction, subagent context isolation. Quantify how much context you're
  currently sending vs. what's needed.
- **Cheaper embeddings** — smaller/cheaper hosted embedding models, or a local/open embedding
  model (embedding cost → compute cost). Compare $/quality.
- **Map-first / lazy reading** — read a cheap structural map, fetch full files only on demand
  (aider repo-map pattern); estimate how much ingestion it avoids.
- **Answer/semantic caching** — cache responses to repeated or near-duplicate questions.

Also study **how comparable tools control cost** (e.g., how Aider budgets its repo map and
context) via the `explore` subagent — take the ideas, cite the source.

**Checkpoint:** a "Techniques" section in `COST-RESEARCH.md`, each lever with mechanism,
current cited savings/pricing, constraints, and quality risk.

## 5. Step 3 — estimate impact against the real profile

Tie each technique to *this system's* measured sinks — a lever that targets a 3%-of-cost stage
doesn't matter, however good in theory.

1. For each lever, estimate expected $/onboarding savings **against the Step 1 profile**
   (e.g., "index persistence removes ~X% because embedding is Y% of repeat-run cost").
2. Score each on **impact × effort × quality-risk**.
3. Flag the genuine tradeoff explicitly: the **cost/quality frontier**. Aggressive routing or
   heavy context compression can drop answer quality — note where, and how you'd guard it
   (which eval metric must not regress). Set a **default quality guardrail** ("no more than a
   2% drop in eval groundedness/citation accuracy") and record it as a decision the human can
   override.

**Checkpoint:** a ranked table (lever · expected savings · effort · quality-risk · how to
validate) in `COST-RESEARCH.md`.

## 6. Step 4 — produce the recommended plan (the handoff)

Synthesize into an executable plan:

1. A **recommended sequence** of levers (biggest impact / lowest risk first) with a target
   total $/onboarding reduction and the guardrail metric that must hold.
2. For each: what to build, how to measure its effect, and the rollback signal if quality
   drops.
3. Anything you'd deliberately *not* do and why (e.g., distillation — too much effort for the
   volume right now).
4. Update `PHASE3.md`'s Phase 1 to reflect this evidence-based order, replacing the assumed
   ordering with the researched one.

**Checkpoint:** `COST-RESEARCH.md` ends with a ranked, sequenced, measurable plan; `PHASE3.md`
Phase 1 updated to match. Commit: `research: cost-reduction plan grounded in real profile`.

## 7. Definition of done

- [ ] `COST-RESEARCH.md` contains: measured current profile (top sinks quantified), a surveyed
      technique catalog with **current, dated** pricing/savings figures, an impact estimate
      tied to the real profile, and a ranked+sequenced recommended plan
- [ ] The cost/quality tradeoff is explicit, with a default guardrail metric recorded
- [ ] `PHASE3.md` Phase 1 updated to the evidence-based sequence
- [ ] No production code changed (research artifacts + throwaway measurement scripts only)
- [ ] Findings summarized: the top 3 sinks, the top 3 levers, and expected total savings

When done, present the summary and the recommended plan, then stop. If the cost/quality
guardrail is a decision the human should weigh in on, surface it clearly as the one place
worth a look before the build proceeds — otherwise proceed with the recorded default into
`PHASE3.md`.

## 8. If blocked

Ask the human only for a secret you can't obtain or a genuine tradeoff decision with no
reasonable default (the cost/quality guardrail is the likely one — but set and record a
sensible default rather than waiting). Otherwise choose, record in `COST-RESEARCH.md`, and
continue.
