# OnboardAgent — self-iteration protocol (standing instruction)

> **How to use.** Add this file to the repo as `ITERATION.md`, and add one line to
> `CLAUDE.md`: *"At the end of every phase, follow ITERATION.md."* From then on the agent
> proposes its own next steps instead of waiting for you to write a brief. You review and
> approve/redirect in plan mode — you become the editor of plans, not the author.

---

## North star (the fixed goal every proposal is measured against)

**OnboardAgent should read any codebase cheaply, accurately, and robustly enough to reason
about acting on it — while staying read-only until code-writing is explicitly authorized.**

Four standing quality dimensions, in priority order. Every self-proposed phase must move at
least one without regressing the others:
1. **Accuracy** — grounded, correctly-cited answers; honest refusal when the code lacks the
   answer.
2. **Cost** — tokens/dollars per onboarding.
3. **Reach & robustness** — languages handled; never crashes on a bad repo.
4. **Usefulness** — how directly it helps a human (or another agent) understand and act.

Do not invent new north stars. If a genuinely new direction seems warranted, propose it as a
question for the human, don't just pursue it.

## The loop (run at the end of every phase)

When a phase's exit criteria pass and it's committed:

1. **Self-assess.** Write a short "Phase N retrospective" in `ROADMAP.md`: what shipped, the
   measured results (eval numbers, cost numbers), what's now weakest against the four
   dimensions, and any debt/risks introduced.
2. **Switch to plan mode** (propose, don't build). Draft the **next phase** as a plan:
   - the single most valuable next step, chosen by (impact on the north star) × (low
     risk/effort) — justify why it beats the alternatives you considered;
   - concrete exit criteria and the metric that proves success;
   - the guardrail metrics that must NOT regress;
   - explicitly, what you are choosing *not* to do next and why.
3. **Update `ROADMAP.md`:** move the retrospective into "Done," put the proposed phase under
   "Proposed — awaiting approval," and keep a running "Backlog / future ideas" list so good
   ideas aren't lost when deferred.
4. **Stop and present** the proposal to the human. Do not build the next phase until approved.
   The human will reply "go", "go but change X", or "do Y instead."

## Approval modes (the human sets the leash length)

The human may grant a wider leash for a run. Honor whichever is stated:
- **Review-each (default):** propose, stop, wait for approval every phase.
- **Run-until-checkpoint:** execute self-proposed phases in sequence, stopping only at a
  checkpoint — defined as any of: a cost/quality tradeoff beyond the recorded guardrail, a
  scope expansion beyond the current north star, an irreversible/destructive action, a new
  external dependency or spend, or leaving read-only. Log each completed phase to `ROADMAP.md`
  as you go.
- **One-phase:** do exactly the approved phase, then return to review-each.

Never widen your own leash. If unsure which mode applies, default to review-each.

## Guardrails on self-direction

- **Scope discipline beats ambition.** A small, verified improvement to the north star beats
  a large speculative feature. Prefer the boring high-impact step.
- **Read-only is invariant** until the human explicitly authorizes code-writing (which
  reopens the sandboxing/safety work — flag that when you propose it).
- **Every proposal is evidence-based.** Anchor it to the latest eval/cost numbers, not vibes.
  If you lack the data to choose, propose a measurement/research spike as the next phase.
- **No silent scope creep, no gold-plating.** If the tool already meets the bar on a
  dimension, don't polish it further — move to the weakest dimension.
- **Surface tradeoffs, don't hide them.** Any cost/quality or scope tradeoff goes in the
  proposal explicitly for the human to weigh.

## `ROADMAP.md` structure (the agent maintains this)

```
# OnboardAgent roadmap
## North star
<the fixed goal + four dimensions>
## Done
- Phase 1 — <name>: shipped <what>; results <numbers>; retrospective <link/notes>
- Phase 2 — ...
## Proposed — awaiting approval
- Phase N — <name>: rationale, exit criteria, guardrails, what's excluded
## Backlog / future ideas
- <deferred ideas with a one-line why-later>
```

Keep `ROADMAP.md` current — it is the project's memory of where it's been and where it's
going, and it's what lets iteration survive across sessions.
