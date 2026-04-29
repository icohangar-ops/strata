"""CompetencyAssessor — handbook-aligned scorecard on the *competency* axis.

Strata's L1 has two axes:

  * Process axis (MaturityAssessor): how well does the finance function run?
    rubric_ids: rb.function.{close, reconcile, board_pack, bva, forecast, ma}

  * Competency axis (this module): how strategic is the CFO?
    rubric_ids: rb.competency.{strategic_leadership, fpna, digital,
                               stakeholder, risk_governance}

Both axes share the same L5 schema and the same RubricScoreReport.compute path.
The difference is just which rubrics are loaded.
"""
from __future__ import annotations

from strata.maturity.assessor import (
    AssessmentResult,
    CapabilitySnapshot,
    MaturityAssessor,
)

COMPETENCY_RUBRIC_IDS: tuple[str, ...] = (
    "rb.competency.strategic_leadership",
    "rb.competency.fpna",
    "rb.competency.digital",
    "rb.competency.stakeholder",
    "rb.competency.risk_governance",
)


class CompetencyAssessor(MaturityAssessor):
    """MaturityAssessor parameterized to the five competency-pillar rubrics."""

    def __init__(self) -> None:
        super().__init__(rubric_ids=COMPETENCY_RUBRIC_IDS)


__all__ = [
    "COMPETENCY_RUBRIC_IDS",
    "CompetencyAssessor",
    "AssessmentResult",
    "CapabilitySnapshot",
]
