"""Board-pack mock author. Deterministic, used in offline mode and tests."""
from __future__ import annotations

from typing import Any

from strata.deliverable.author import build_author_prompt  # re-exported for back-compat
from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["build_author_prompt", "mock_author"]


_CUE_BANK = [
    "tie", "ledger", "reconciling", "comparatives", "restated", "currency",
    "driver", "volume", "price", "mix", "owner", "action", "materiality",
    "bridge", "scenario", "downside", "upside", "headline", "decision-required",
    "FYI", "FYA",
]


def mock_author(
    persona: Persona,
    rubric: Rubric,
    inputs: dict[str, Any],
    history: list[GraderResult],
) -> str:
    """Deterministic author whose drafts grow more rubric-compliant each iteration."""
    iteration = len(history) + 1
    period = inputs.get("period", "Period")
    company = inputs.get("company", "Company")
    revenue = inputs.get("revenue_actual", "n/a")
    revenue_b = inputs.get("revenue_budget", "n/a")
    cue_count = min(len(_CUE_BANK), 4 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# {company} — {rubric.name} — {period}\n\n"
        f"## Headline\nRevenue actual {revenue} vs budget {revenue_b}.\n\n"
        f"## Numerical integrity\nNumbers tie to ledger. Comparatives restated where reclass occurred. "
        f"Currency and units labeled.\n\n"
        f"## Variance narrative\nVariances attributed to driver: volume, price, mix. "
        f"Owners and actions assigned to each adverse line. Materiality threshold disclosed.\n\n"
        f"## Forward view\nForecast revision bridge from prior. Scenario disclosure: base, upside, downside.\n\n"
        f"## Decisions\nFYI / FYA / decision-required asks listed with CFO recommendation.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
