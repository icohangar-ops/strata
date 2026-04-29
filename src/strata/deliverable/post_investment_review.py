"""Post-investment review mock author. Deterministic, used in offline mode."""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "actual", "projected", "delta", "IRR", "payback", "cumulative",
    "decomposition", "volume", "price", "mix", "timing", "one-time",
    "quantified", "blame-free", "decisions", "assumptions", "system-level",
    "verdict", "yes-with-changes", "lessons", "owner", "checklist",
    "hurdle", "template", "update", "continue", "kill", "double-down",
    "council", "board", "escalated", "cadence",
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
    review_window = inputs.get("review_window_months", 12)
    actual_irr = inputs.get("actual_irr_pct", "n/a")
    projected_irr = inputs.get("projected_irr_pct", "n/a")
    cue_count = min(len(_CUE_BANK), 5 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# Post-Investment Review - {project} - {company}\n"
        f"Window: {review_window} months\n\n"
        f"## Attribution rigor\nIRR actual {actual_irr}% vs projected {projected_irr}% "
        f"(delta quantified, absolute and %). Cumulative cash and payback shown vs plan. "
        f"Variance decomposed into volume, price, mix, timing, and one-time items with "
        f"quantified contribution.\n\n"
        f"## Honest assessment\nFindings name decisions and assumptions, not people; failure modes "
        f"documented as system-level lessons. Would-we-redo verdict explicit (yes / no / "
        f"yes-with-changes) with named conditions.\n\n"
        f"## Learning capture\nEach lesson states what changed, who owns it, and which checklist / "
        f"hurdle / template gets updated. Specific changes proposed and routed for approval.\n\n"
        f"## Forward action\nExplicit continue / kill / double-down decision with capital "
        f"implications and timeline. Lessons routed to capital council; material findings escalated "
        f"to board; cadence for next review set.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
