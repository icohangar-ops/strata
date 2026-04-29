"""Earnings script mock author. Deterministic, used in offline mode."""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "spoken-word", "pacing", "transitions", "tested", "headline",
    "narrated", "drove", "safe-harbor", "forward-looking", "assumptions",
    "guidance", "bridge", "prior", "changed", "capital", "deployed",
    "ROIC", "trajectory", "analyst", "questions", "rehearsed",
    "protocol", "disclose", "follow", "off-script",
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
    revenue = inputs.get("revenue_m", "n/a")
    cue_count = min(len(_CUE_BANK), 5 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# {company} - Earnings Call Script - {period}\n\n"
        f"## Prepared remarks (8 min spoken)\n"
        f"[Safe-harbor: forward-looking statements wrapped; assumptions named explicitly.]\n\n"
        f"Revenue ${revenue}M -- driven by [drivers in 1-2 narrated sentences]. "
        f"Each headline number stated then narrated; no unsupported claims. "
        f"Spoken-word pacing tested; remarks <= 8 minutes; transitions tested aloud.\n\n"
        f"## Guidance\n"
        f"Any change to prior guidance has a quantified bridge: prior -> what changed -> new. "
        f"Forward-looking statements bracketed by safe-harbor language; assumptions named.\n\n"
        f"## Capital allocation\n"
        f"Clear narrative on how capital was deployed this quarter and why; ties to ROIC trajectory.\n\n"
        f"## Q&A rehearsal\n"
        f"Top 10 likely analyst questions drafted with crisp answers; tough questions surfaced and "
        f"rehearsed. Pre-agreed phrases for 'we do not disclose that' and 'we will follow up' to "
        f"avoid off-script disclosures.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
