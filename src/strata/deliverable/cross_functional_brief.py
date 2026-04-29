"""Cross-functional brief mock author. Deterministic, used in offline mode."""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "timeboxed", "sections", "performance", "review", "pipeline",
    "dependencies", "decision-support", "standing", "win-rate", "ACV",
    "cycle", "time", "yield", "OEE", "activation", "retention",
    "decisions", "owner", "options", "recommendation", "deadline",
    "carry-forward", "aging", "cadence", "protected", "rescheduled",
]


_PEER_METRICS = {
    "sales":      ["pipeline", "win-rate", "ACV"],
    "operations": ["cycle time", "yield", "OEE"],
    "product":    ["activation", "retention", "feature adoption"],
    "marketing":  ["pipeline-sourced", "CAC", "channel mix"],
}


def mock_author(
    persona: Persona,
    rubric: Rubric,
    inputs: dict[str, Any],
    history: list[GraderResult],
) -> str:
    iteration = len(history) + 1
    company = inputs.get("company", "Company")
    peer_function = str(inputs.get("peer_function", "sales")).lower()
    period = inputs.get("period", "Period")
    peer_metrics = ", ".join(_PEER_METRICS.get(peer_function, _PEER_METRICS["sales"]))
    cue_count = min(len(_CUE_BANK), 5 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# {company} - CFO x {peer_function.title()} Bi-Weekly Brief - {period}\n"
        f"Total: 30 minutes (28 timeboxed + 2 soft close)\n\n"
        f"## Section 1 - Business performance review (10 min)\n"
        f"Frame in {peer_function} vocabulary: {peer_metrics}. "
        f"Period-over-period and vs plan. Carry-forwards from last meeting reviewed.\n\n"
        f"## Section 2 - Pipeline / dependencies (10 min)\n"
        f"Cross-team dependencies tracked with named owners across both teams.\n\n"
        f"## Section 3 - Decision-support items (8 min)\n"
        f"Each open decision: owner, options, recommendation, deadline.\n\n"
        f"## Soft close (2 min)\n"
        f"Action items: every item has owner, due date, and is reviewed next meeting; aging tracked. "
        f"Cadence: standing meeting slot held; cancellations exceptional and rescheduled same week.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
