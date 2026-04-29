"""L1 — Maturity Assessor.

Takes a capability rubric and a set of self-reported scores (or LLM-graded
scores) and produces a normalized maturity heatmap. Reuses the L5 schema,
no new code paths.

For the MVP the assessor is fed scores directly (e.g. from a CLI prompt or
a static YAML of self-reported answers). The same RubricScoreReport.compute
path is used as for deliverables, proving the schema unification.
"""
from __future__ import annotations

from dataclasses import dataclass

from strata import registry
from strata.schema import (
    CharacteristicScore,
    Rubric,
    RubricScoreReport,
)

CAPABILITY_RUBRIC_IDS: tuple[str, ...] = (
    "rb.function.close",
    "rb.function.reconcile",
    "rb.function.board_pack",
    "rb.function.bva",
    "rb.function.forecast",
    "rb.function.ma",
    "rb.function.risk",
    "rb.function.capital_allocation",
)


@dataclass(frozen=True)
class CapabilitySnapshot:
    rubric: Rubric
    report: RubricScoreReport

    @property
    def name(self) -> str:
        return self.rubric.name

    @property
    def score_pct(self) -> float:
        return self.report.normalized_pct


@dataclass(frozen=True)
class AssessmentResult:
    target_id: str
    capabilities: tuple[CapabilitySnapshot, ...]

    @property
    def overall_pct(self) -> float:
        if not self.capabilities:
            return 0.0
        return sum(c.score_pct for c in self.capabilities) / len(self.capabilities)

    def heatmap(self) -> list[tuple[str, float]]:
        return sorted(((c.name, c.score_pct) for c in self.capabilities), key=lambda x: x[1])


class MaturityAssessor:
    """Scores a finance function across the registered capability rubrics."""

    def __init__(self, rubric_ids: tuple[str, ...] = CAPABILITY_RUBRIC_IDS) -> None:
        self.rubric_ids = rubric_ids

    def assess(
        self,
        target_id: str,
        scores_by_rubric: dict[str, list[CharacteristicScore]],
        pass_threshold_pct: float = 70.0,
        tenant_id: str | None = None,
    ) -> AssessmentResult:
        snapshots: list[CapabilitySnapshot] = []
        for rid in self.rubric_ids:
            rubric = registry.get(rid)
            scores = scores_by_rubric.get(rid)
            if scores is None:
                raise ValueError(f"missing scores for capability '{rid}'")
            if tenant_id:
                from strata.maturity.overrides import apply_overrides, load_overrides
                rubric, scores = apply_overrides(
                    rubric, scores, load_overrides(tenant_id, rid)
                )
            report = RubricScoreReport.compute(
                rubric=rubric,
                target_id=target_id,
                scores=scores,
                pass_threshold_pct=pass_threshold_pct,
            )
            snapshots.append(CapabilitySnapshot(rubric=rubric, report=report))
        return AssessmentResult(target_id=target_id, capabilities=tuple(snapshots))

    @staticmethod
    def baseline_scores(rubric: Rubric, score: int = 2) -> list[CharacteristicScore]:
        """Helper: produce a uniform baseline score across all characteristics in a rubric.

        Useful for new-customer onboarding: 'rate yourself a 2 across the board, then
        adjust upward where you have evidence'.
        """
        out: list[CharacteristicScore] = []
        for group in rubric.groups:
            for char in group.characteristics:
                out.append(
                    CharacteristicScore(
                        characteristic_id=char.id,
                        score=score,
                        rationale="baseline",
                    )
                )
        return out
