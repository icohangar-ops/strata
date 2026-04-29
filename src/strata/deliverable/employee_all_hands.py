"""Employee all-hands mock author. Deterministic, used in offline mode."""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "plain", "English", "jargon", "outcomes", "ten-minute", "time-budget",
    "visual", "concept", "conclusion", "title", "infographic", "templated",
    "branded", "palette", "readable", "growth", "unblocked", "customer",
    "project", "hire", "wins", "lessons", "credited", "anticipated",
    "questions", "sensitive", "confidentiality", "boundary", "disclosed",
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
    duration = inputs.get("target_duration_minutes", 10)
    cue_count = min(len(_CUE_BANK), 5 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# {company} - All-Hands Finance Segment - {period}\n"
        f"Target duration: {duration} minutes\n\n"
        f"## Plain English\n"
        f"Zero finance jargon; every term has a one-line plain-English equivalent. "
        f"Speakable in {duration} minutes with explicit time-budget per section.\n\n"
        f"## Visual storytelling\n"
        f"One visual per concept, not per data point; every chart titled with its conclusion. "
        f"Templated, branded visuals; consistent palette; readable from the back of the room.\n\n"
        f"## How finance enables growth\n"
        f"Specific examples of how finance unblocked growth this period: one customer, one project, "
        f"one hire. Wins AND lessons named specifically; people credited where appropriate.\n\n"
        f"## Q&A readiness\n"
        f"Top 5 likely employee questions prepared with crisp answers; sensitive topics flagged. "
        f"What can / cannot be shared explicitly disclosed; reasons given without breach.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
