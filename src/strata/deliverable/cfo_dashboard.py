"""CFO value-creation dashboard mock author. Deterministic, used in offline mode."""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "economic", "value", "added", "trailing", "trend", "spread",
    "ROIC", "WACC", "free", "cash", "flow", "segmented", "segment",
    "gross", "margin", "working", "capital", "DSO", "DPO", "DIO",
    "conversion", "cycle", "likelihood", "impact", "owner",
    "control", "adequate", "remediating", "pipeline", "stage",
    "hurdle", "deployed", "weighted", "portfolio",
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
    eva = inputs.get("eva_m", "n/a")
    roic = inputs.get("roic_pct", "n/a")
    wacc = inputs.get("wacc_pct", "n/a")
    fcf = inputs.get("fcf_m", "n/a")
    cue_count = min(len(_CUE_BANK), 5 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# {company} — CFO Dashboard — {period}\n\n"
        f"## Value creation\n"
        f"Economic Value Added: ${eva}M (trailing-12-month trend shown). "
        f"ROIC {roic}% vs WACC {wacc}% — spread {(_pct(roic) - _pct(wacc)):.1f}%. "
        f"Free cash flow ${fcf}M with YoY comparison.\n\n"
        f"## Operating performance\n"
        f"Revenue growth segmented by product and customer with mix shift. "
        f"Gross margin segmented by customer segment. "
        f"Working capital days: DSO, DPO, DIO trended with cash-conversion-cycle computed.\n\n"
        f"## Risk dashboard\n"
        f"Top 5 risks with likelihood x impact heat score, owner named, control status "
        f"(adequate / remediating / gap) visible per risk.\n\n"
        f"## Capital pipeline\n"
        f"Capital project pipeline with stage, expected ROI vs hurdle, capital deployed, "
        f"and decision date. Portfolio view: total deployed, weighted-average ROI, risk distribution.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )


def _pct(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
