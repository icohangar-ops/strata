"""3-statement model mock author. Deterministic, used in offline mode and tests.

The 'draft' here is a model spec / build plan written in markdown; an LLM
backend would either emit Excel-formula scaffolding or python (pandas / openpyxl)
glue to render the actual workbook. The rubric grades the spec equally.
"""
from __future__ import annotations

from typing import Any

from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric

__all__ = ["mock_author"]


_CUE_BANK = [
    "retained", "earnings", "depreciation", "accumulated", "indirect",
    "method", "deltas", "reconciles", "rounding", "inputs", "labeled",
    "units", "source", "hardcodes", "formulas", "toggle", "named",
    "single", "scenario", "sensitivity", "two-way", "drivers",
    "auto-refresh", "balance", "assets", "liabilities", "equity",
    "conditional", "flag", "tie-out", "filed", "financials", "links",
]


def mock_author(
    persona: Persona,
    rubric: Rubric,
    inputs: dict[str, Any],
    history: list[GraderResult],
) -> str:
    iteration = len(history) + 1
    company = inputs.get("company", "Company")
    horizon = inputs.get("forecast_horizon_years", 5)
    scenarios = inputs.get("scenarios", ["base", "upside", "downside"])
    cue_count = min(len(_CUE_BANK), 5 * iteration)
    cues = " ".join(_CUE_BANK[:cue_count])
    return (
        f"# {company} — Three-Statement Model — {horizon}Y horizon\n\n"
        f"## Linking integrity\nNet income flows to retained earnings. "
        f"D&A flows to PP&E and accumulated depreciation. Indirect-method cash flow derives "
        f"from P&L + balance-sheet deltas; ending cash on CF reconciles to BS cash to the dollar.\n\n"
        f"## Driver structure\nInputs sheet separated; each driver labeled with units and source. "
        f"Hardcodes only on inputs sheet; formula cells are pure formulas.\n\n"
        f"## Scenarios\nScenario toggle drives all variable inputs from a single named cell. "
        f"Scenarios: {', '.join(scenarios)}. Two-way sensitivity tables on top three drivers; "
        f"auto-refresh on input change.\n\n"
        f"## Validation\nAssets = Liabilities + Equity check on every period with conditional flag. "
        f"Source-document tie-out tab; each historical input links to filed financials.\n\n"
        f"<!-- iter={iteration} cues: {cues} -->\n"
    )
