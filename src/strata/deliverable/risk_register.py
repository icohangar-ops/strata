"""Risk register mock author. Deterministic, used in offline mode."""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "financial", "operational", "strategic", "compliance", "cyber",
    "reputational", "ESG", "category", "business", "unit", "calibrated",
    "anchors", "likelihood", "impact", "heat", "score", "threshold",
    "escalation", "movement", "controls", "effectiveness", "tested",
    "gap", "owner", "remediation", "deadline", "committee", "quarterly",
    "appetite", "out-of-appetite",
]


def mock_author(
    persona: Persona,
    rubric: Rubric,
    inputs: dict[str, Any],
    history: list[GraderResult],
) -> str:
    iteration = len(history) + 1
    company = inputs.get("company", "Company")
    period = inputs.get("period", "Period")
    appetite = inputs.get("risk_appetite_summary", "(appetite statement pending)")
    cue_count = min(len(_CUE_BANK), 5 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# {company} - Enterprise Risk Register - {period}\n\n"
        f"## Risk appetite\n{appetite}\n\n"
        f"## Coverage\nAll seven categories represented: financial, operational, strategic, "
        f"compliance, cyber, reputational, ESG. Each business unit contributes risks; "
        f"functional risks identified separately from operational.\n\n"
        f"## Scoring\nLikelihood (1-5) and impact (1-5) scored with calibration anchors disclosed. "
        f"Heat score = likelihood x impact; threshold > 15 escalates to board. "
        f"Movement vs prior period flagged.\n\n"
        f"## Control mapping\nEach high-heat risk lists existing controls with effectiveness score "
        f"and last test date. Every control gap pairs with named remediation owner and deadline.\n\n"
        f"## Governance\nTop risks routed to risk committee; quarterly review cadence. "
        f"Each risk's heat score compared to appetite; out-of-appetite risks flagged for action.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
