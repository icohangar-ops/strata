"""BvA commentary mock author. Deterministic, used in offline mode and tests."""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "volume", "price", "mix", "decomposition", "owner", "action",
    "target", "threshold", "materiality", "favorable", "unfavorable",
    "one-time", "non-recurring", "reforecast", "bridge", "trailing",
    "rolling", "trend", "quantified",
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
    threshold = inputs.get("materiality_threshold_pct", 5)
    cue_count = min(len(_CUE_BANK), 4 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# {company} — {rubric.name} — {period}\n\n"
        f"## Materiality\nMateriality threshold: {threshold}% of budgeted line. "
        f"Variances below threshold are not narrated.\n\n"
        f"## Driver attribution\nRevenue variance decomposed into volume, price, and mix with quantified contribution. "
        f"One-time items (settlement, severance) isolated from run-rate.\n\n"
        f"## Ownership and action\nMaterial variances have named owners and target close dates. "
        f"Adverse variances paired with specific action and ETA.\n\n"
        f"## Threshold and signs\nFavorable / unfavorable signed convention applied with legend.\n\n"
        f"## Forward bridge\nPersistent variances bridged into reforecast with quantified impact. "
        f"Trailing-3-month and YoY rolling-trend context included.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
