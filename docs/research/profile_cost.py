"""Phase 3 cost research spike: profile a real onboarding + multi-question session's actual
dollar/token cost by stage. Run with: `uv run python docs/research/profile_cost.py`.

Reuses the already-cached pallets/flask fixture (see evals/fixtures/flask.yaml) rather than
ingesting a new repo, so this script's own cost is limited to the live-answer calls it makes --
ingestion/embedding is a cache hit and therefore $0 by construction (see docs/PLAN.md decision
#14). This is a throwaway measurement script, not part of the shipped package -- it lives under
docs/ (not src/) so it's never imported or packaged, but it IS committed so the profiled numbers
in docs/COST-RESEARCH.md stay reproducible.

Pricing constants below are deliberately left as placeholders: per docs/PHASE3.md, dollar figures
must come from live, dated research (Step 2 of the spike), never remembered numbers. The script
runs and prints token counts immediately either way; the $ columns are only computed once the
constants are filled in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from onboard_agent.agent.loop import ask_onboarding_question
from onboard_agent.agent.overview import generate_overview
from onboard_agent.evals.harness import load_fixture
from onboard_agent.ingestion.pipeline import get_or_ingest_repo_context
from onboard_agent.tools.schemas import UsageTotals

FIXTURE_PATH = Path(__file__).parent.parent.parent / "src/onboard_agent/evals/fixtures/flask.yaml"

# USD per million tokens for claude-sonnet-5 (this project's ONBOARD_AGENT_MODEL override --
# see agent_model()/config.py; the shipped default is claude-opus-5, priced $5/$25/$6.25/$0.50).
# Source: https://www.claude.com/pricing and
# https://platform.claude.com/docs/en/build-with-claude/prompt-caching, observed 2026-09-19.
# Cache write here is the 5-minute-TTL rate (1.25x input); Anthropic also offers a 1-hour-TTL
# write at 2x input for longer-lived sessions, not used by this project today.
PRICE_PER_MTOK_INPUT: float | None = 2.00
PRICE_PER_MTOK_OUTPUT: float | None = 10.00
PRICE_PER_MTOK_CACHE_WRITE: float | None = 2.50
PRICE_PER_MTOK_CACHE_READ: float | None = 0.20


@dataclass
class StageProfile:
    label: str
    one_time: bool
    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    wall_seconds: float = 0.0

    def add_usage(self, usage: UsageTotals) -> None:
        self.api_calls += usage.api_calls
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.cache_creation_input_tokens += usage.cache_creation_input_tokens
        self.cache_read_input_tokens += usage.cache_read_input_tokens

    def dollar_cost(self) -> float | None:
        prices = (
            PRICE_PER_MTOK_INPUT,
            PRICE_PER_MTOK_OUTPUT,
            PRICE_PER_MTOK_CACHE_WRITE,
            PRICE_PER_MTOK_CACHE_READ,
        )
        if any(p is None for p in prices):
            return None
        return (
            self.input_tokens * PRICE_PER_MTOK_INPUT
            + self.output_tokens * PRICE_PER_MTOK_OUTPUT
            + self.cache_creation_input_tokens * PRICE_PER_MTOK_CACHE_WRITE
            + self.cache_read_input_tokens * PRICE_PER_MTOK_CACHE_READ
        ) / 1_000_000


@dataclass
class Profile:
    stages: list[StageProfile] = field(default_factory=list)

    def total_dollar_cost(self) -> float | None:
        costs = [s.dollar_cost() for s in self.stages]
        if any(c is None for c in costs):
            return None
        return sum(costs)


def run_profile() -> Profile:
    profile = Profile()

    repo_url, questions = load_fixture(FIXTURE_PATH)
    answerable = [q for q in questions if q.answerable]

    ingestion = StageProfile(label="Ingestion & embedding (cache hit)", one_time=True)
    t0 = time.monotonic()
    ctx = get_or_ingest_repo_context(repo_url)
    ingestion.wall_seconds = time.monotonic() - t0
    profile.stages.append(ingestion)

    ask_first = StageProfile(
        label="ask_onboarding_question (1st call, cache write)", one_time=False
    )
    ask_rest = StageProfile(
        label="ask_onboarding_question (later calls, cache read)", one_time=False
    )
    for i, q in enumerate(answerable):
        t0 = time.monotonic()
        result = ask_onboarding_question(q.question, ctx)
        elapsed = time.monotonic() - t0
        target = ask_first if i == 0 else ask_rest
        target.add_usage(result.usage)
        target.wall_seconds += elapsed
        print(f"  asked [{i + 1}/{len(answerable)}]: {q.question[:60]!r} -> {result.usage}")
    profile.stages.append(ask_first)
    profile.stages.append(ask_rest)

    overview_stage = StageProfile(label="generate_overview (1 call)", one_time=False)
    t0 = time.monotonic()
    overview_result = generate_overview(ctx)
    overview_stage.wall_seconds = time.monotonic() - t0
    overview_stage.add_usage(overview_result.usage)
    profile.stages.append(overview_stage)

    return profile


def print_table(profile: Profile) -> None:
    header = (
        f"{'Stage':<45} {'1x/rpt':<7} {'calls':>5} {'in_tok':>8} {'out_tok':>8} "
        f"{'cache_w':>8} {'cache_r':>8} {'$ cost':>10} {'% total':>8} {'wall_s':>7}"
    )
    print(header)
    print("-" * len(header))
    total_cost = profile.total_dollar_cost()
    for s in profile.stages:
        cost = s.dollar_cost()
        cost_str = f"${cost:.4f}" if cost is not None else "n/a"
        pct_str = f"{cost / total_cost:.0%}" if cost is not None and total_cost else "n/a"
        print(
            f"{s.label:<45} {'one-time' if s.one_time else 'repeat':<7} {s.api_calls:>5} "
            f"{s.input_tokens:>8} {s.output_tokens:>8} {s.cache_creation_input_tokens:>8} "
            f"{s.cache_read_input_tokens:>8} {cost_str:>10} {pct_str:>8} {s.wall_seconds:>6.1f}s"
        )
    if total_cost is not None:
        print("-" * len(header))
        print(f"{'TOTAL':<45} {'':<7} {'':>5} {'':>8} {'':>8} {'':>8} {'':>8} ${total_cost:.4f}")
    else:
        print("\n(Pricing constants not yet filled in -- $ columns show n/a. Token counts above")
        print(
            " are real and complete; fill PRICE_PER_MTOK_* from Step 2's live research to get $.)"
        )


if __name__ == "__main__":
    profile = run_profile()
    print()
    print_table(profile)
