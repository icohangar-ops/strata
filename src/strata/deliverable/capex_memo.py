"""Capex memo mock author. Deterministic, used in offline mode."""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "thesis", "strategic", "fit", "sponsor", "alternative", "build",
    "partner", "defer", "IRR", "hurdle", "payback", "ceiling",
    "sensitivity", "two-way", "drivers", "downside", "ranked",
    "impact", "likelihood", "mitigation", "owner", "gating",
    "cannibalization", "substitution", "quantified", "tranche",
    "schedule", "look-back", "review", "committed",
]


def mock_author(
    persona: Persona,
    rubric: Rubric,
    inputs: dict[str, Any],
    history: list[GraderResult],
) -> str:
    iteration = len(history) + 1
    company = inputs.get("company", "Company")
    project = inputs.get("project_name", "Project")
    capital = inputs.get("capital_request_m", "n/a")
    irr = inputs.get("expected_irr_pct", "n/a")
    hurdle = inputs.get("hurdle_irr_pct", 20)
    cue_count = min(len(_CUE_BANK), 5 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# Capex Memo - {project} - {company}\n\n"
        f"## Recommendation\nApprove ${capital}M, tranche schedule below; gating events between "
        f"tranches; defer if gates fail. 12-month and 24-month look-back committed; named review owner.\n\n"
        f"## Thesis and strategic fit\nSingle-sentence thesis tied to strategy with strategic-fit "
        f"score >= 7/10 and named sponsor. Considered alternatives (build / partner / defer) with explicit "
        f"reason for choosing this.\n\n"
        f"## Financial rigor\nExpected IRR {irr}% vs hurdle {hurdle}%; payback within ceiling. "
        f"Two-way sensitivity table on the three drivers most affecting IRR; downside case bounded.\n\n"
        f"## Risk transparency\nTop 3 risks ranked by impact x likelihood; each has named mitigation "
        f"owner and pre-funding gating action. Cannibalization quantified; net effect computed.\n\n"
        f"## Decision frame\nTotal capital, tranche schedule, gating events; deferral plan if gates fail.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
