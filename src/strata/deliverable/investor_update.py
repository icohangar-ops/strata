"""Investor update mock author. Deterministic, used in offline mode and tests."""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "metrics", "headline", "consistent", "restated", "footnoted",
    "definitions", "published", "deviations", "wins", "losses", "named",
    "specifically", "learned", "commitments", "tracked", "actual",
    "explained", "specific", "deadline", "bounded", "routed",
    "investor", "network", "segmentation", "prior", "year",
    "comparisons", "appendix", "signal",
]


def mock_author(
    persona: Persona,
    rubric: Rubric,
    inputs: dict[str, Any],
    history: list[GraderResult],
) -> str:
    iteration = len(history) + 1
    period = inputs.get("period", "Period")
    company = inputs.get("company", "Company")
    arr = inputs.get("arr", "n/a")
    runway = inputs.get("runway_months", "n/a")
    cue_count = min(len(_CUE_BANK), 5 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# {company} — Investor Update — {period}\n\n"
        f"## Headline metrics\nARR ${arr} (vs prior period and same-period-last-year). "
        f"Runway {runway} months. Same headline metrics every period; restatements footnoted.\n\n"
        f"## Wins and losses\nWins led; losses named specifically with what was learned. "
        f"Prior-period commitments tracked vs actual with gaps explained.\n\n"
        f"## Definitions\nMetric definitions published once; deviations called out.\n\n"
        f"## Period-over-period\nThree to five KPIs only; same KPIs every period; "
        f"everything else is appendix. Metrics shown vs prior and same-period-last-year.\n\n"
        f"## Asks\nSpecific asks: named role, named target company, bounded, with deadline. "
        f"Asks routed by investor drawing on each investor's network.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
