# OnboardAgent — Phase 2 build brief (prove, extend, demo)

> **How to use.** Drop this in the existing OnboardAgent repo as `PHASE2.md`, open Claude
> Code there, and send: *"Read PHASE2.md and execute it end to end. Follow the operating
> protocol exactly."* This builds on the completed v1 scaffold — do not rebuild it.

---

## 1. Mission

v1 proved OnboardAgent *runs*. Phase 2 proves it *works well*, then makes it *demoable*. In
priority order: (1) harden and measure the core against real repos, (2) add automatic
"codebase overview" generation, (3) add a thin web UI for demos, (4) make it usable daily as
an MCP server inside Claude Code itself. Ship each phase to a verified, working state.

## 2. Operating protocol — same as v1

Act as an autonomous staff engineer who automates everything:
- **Re-orient first.** Read the existing `PLAN.md`, `TODO.md`, `README.md`, and the codebase
  before touching anything. Extend the existing architecture; don't duplicate or rewrite it.
- **Plan, then build.** Append a Phase 2 section to `PLAN.md` and `TODO.md` before coding.
- **Phase-gated + self-verifying.** Don't advance until the current phase's exit criteria
  pass. You run the tests/evals yourself.
- **Delegate** to the existing subagents (`explore`, `code-reviewer`, `test-author`).
- **Only stop if truly blocked** (missing secret, no-default product call, external account).
  Otherwise pick the sensible default, record it in `PLAN.md`, and continue.
- **Verify current facts.** For any new dependency (a UI framework, etc.), check its current
  version/API from its docs before writing against it — don't trust remembered APIs.
- **Conventional commits** at each phase boundary; keep the history readable.

## 3. Scope — hold the line

**In scope:** evaluation on real repos; a codebase-overview feature; a thin demo UI; MCP
self-integration. **Still out of scope (record as future work):** writing/proposing code
changes, non-Python repos, multi-repo indexing, auth/multi-user, cloud deployment (that's a
later hardening phase). Read-only remains the invariant.

## 4. Phase 1 — prove the core (highest priority, do this first)

Do **not** build new features until the core is measured. A UI over unproven retrieval is
worthless.

1. Pick **4–5 real, well-known Python repos** of varying shape (e.g., a web framework, an
   API service, a CLI tool, a data library) — choose ones with clear structure so ground
   truth is knowable.
2. For each, write **8–12 onboarding questions** with known-good answers / known relevant
   files (use the `explore` subagent to establish ground truth). Include 1–2 questions the
   repo *cannot* answer, to test honest refusal.
3. Run OnboardAgent across all of them and **do real error analysis**: for every wrong or
   weak answer, label *how* it failed (retrieval missed the file / right file wrong lines /
   hallucinated / should have refused but didn't). Cluster into a failure taxonomy.
4. **Fix the top 1–2 failure modes** (usually chunking or retrieval tuning), and re-measure.
5. Record everything in `EVALS.md`: per-repo metrics (retrieval accuracy, citation
   correctness, groundedness, refusal accuracy), the failure taxonomy, and before/after
   numbers for your fixes.

**Exit criteria:** `EVALS.md` shows measured performance across ≥4 real repos with a
before/after improvement on at least one failure mode. Commit: `test: baseline + improve
core retrieval across real repos`.

## 5. Phase 2 — codebase overview generation (best demo-per-effort)

Add a feature that, given a repo, generates a **structured onboarding document** rather than
only answering ad-hoc questions: architecture summary, key modules and their roles, the
directory map, entry points, how to run/test it, and "where a new engineer should start."
This showcases breadth in a single output and reuses the existing retrieval/agent layer.

- Ground every claim in cited files — the overview must be as citation-honest as the Q&A.
- Add it as a new capability on the agent and as an MCP tool (`generate_overview(repo)`),
  following the `add-retrieval-tool` skill's procedure.
- Add it to the eval harness: does the overview correctly identify the real entry points and
  key modules on your fixture repos?

**Exit criteria:** `generate_overview` produces an accurate, cited onboarding doc for a real
repo; an eval check verifies it identifies known entry points/modules. Commit: `feat: codebase
overview generation`.

## 6. Phase 3 — thin web UI (for demos)

Now — and only now — add a **deliberately thin** web interface over the existing API/agent.
The value is the demo, not frontend engineering; do not over-build.

- Flow: paste a GitHub URL → it ingests → user asks questions and/or requests an overview →
  answers render **with clickable citations that resolve to the file + line range**.
- **Default to the fastest Python-native path** (a Streamlit or Gradio app hitting your
  existing code) unless there's a clear reason to build a proper SPA. Verify the framework's
  current version/API before writing. Keep it to one screen.
- Show retrieval provenance in the UI (which files were used) — it makes the tool feel
  trustworthy and demos the citation quality.

**Exit criteria:** a running local web app where you paste a repo URL and get cited answers +
an overview; citations are visible and correct. Commit: `feat: thin web UI for demos`.

## 7. Phase 4 — dogfood as an MCP server in Claude Code + finalize

Make OnboardAgent a tool you actually use, and wrap up.

1. Ensure the MCP server is cleanly registerable in an external Claude Code instance;
   document the exact registration steps in the README so *you* (or anyone) can add it to
   their own Claude Code and use `search_codebase` / `ask_onboarding_question` /
   `generate_overview` while working.
2. Update `README.md`: what it is, setup, how to run the CLI + UI, how to register it as an
   MCP server, the architecture diagram, and the `EVALS.md` results summary. Add an honest
   "limitations & v2 next-steps" section (code-writing, multi-language, multi-repo, deploy).
3. Confirm a fresh clone + `uv sync` reproduces everything and the full test + eval suite is
   green.

**Exit criteria:** README documents MCP self-registration; fresh clone reproduces; all tests
+ evals pass. Commit: `docs: finalize OnboardAgent Phase 2`.

## 8. Definition of done (self-check)

- [ ] Core measured on ≥4 real Python repos, with a failure taxonomy and a before/after fix
- [ ] `generate_overview` produces accurate, cited onboarding docs, covered by an eval
- [ ] A thin web UI: paste URL → cited answers + overview, citations resolve to file/line
- [ ] OnboardAgent registerable + usable as an MCP server in Claude Code, documented
- [ ] `EVALS.md` and `README.md` complete and honest about limitations
- [ ] Fresh clone reproduces; full test + eval suite green; clean commit history

When every box is checked, summarize: the eval numbers, what improved after error analysis,
the decisions you made autonomously, and the v2 next-steps — then stop.

## 9. If blocked

Ask the human only for a secret you can't obtain, a product decision with no reasonable
default, or an external account you can't create. State the blocker, the options, and your
recommended default. Otherwise choose, record it in `PLAN.md`, and keep going.
