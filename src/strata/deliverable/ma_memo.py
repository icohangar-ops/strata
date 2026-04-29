"""M&A IC memo mock author. Deterministic, used in offline mode and tests."""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "thesis", "strategy", "stakeholder", "synergy", "timing", "owner",
    "workstream", "sensitivity", "quality", "earnings", "adjustments",
    "bridge", "pro-forma", "triangulated", "multiples", "discounted",
    "ranked", "impact", "likelihood", "deal-breaker", "mitigation",
    "gating", "approve", "reject", "conditional", "walk-away",
    "committed", "post-LOI",
]


def mock_author(
    persona: Persona,
    rubric: Rubric,
    inputs: dict[str, Any],
    history: list[GraderResult],
) -> str:
    iteration = len(history) + 1
    target_name = inputs.get("target_name", "Target Co")
    acquirer = inputs.get("acquirer", "Acquirer Inc")
    headline_price = inputs.get("headline_purchase_price_m", "n/a")
    cue_count = min(len(_CUE_BANK), 5 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# IC Memo — Proposed Acquisition of {target_name} by {acquirer}\n\n"
        f"## Recommendation\nApprove-conditional at ${headline_price}M; "
        f"named conditions and walk-away terms below. Pre-committed walk-away price set.\n\n"
        f"## Strategic thesis\nSingle-sentence thesis: {target_name} closes {acquirer}'s "
        f"capability gap in core market. Strategy linkage stated; named stakeholder owner.\n\n"
        f"## Synergy substantiation\nEach synergy line: dollar size, timing, owner, source "
        f"workstream, sensitivity. Pro-forma EBITDA bridge shown.\n\n"
        f"## Financial diligence\nQoE adjustments listed line by line with rationale. "
        f"Triangulated DCF + peer multiples + transaction multiples; sensitivity to top 3 drivers.\n\n"
        f"## Risk assessment\nTop 5 risks ranked by impact x likelihood; deal-breaker line drawn. "
        f"Each risk has named mitigation, owner, and pre-close gating action.\n\n"
        f"## Decision frame\nApprove-conditional. Walk-away price, terms, and post-LOI conditions; "
        f"signed by IC chair.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
