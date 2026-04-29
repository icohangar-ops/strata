"""
L5 — Canonical rubric schema.

A rubric has the same shape regardless of whether it scores a *deliverable*
(L4) or a *function capability* (L1):

    Rubric
      groups: list[Group]                # weighted top-level dimensions
        characteristics: list[Char]      # weighted sub-criteria within a group
          attributes: list[Attribute]    # discrete level-anchors (Strong .. Weak)

Weights at every level are bounded [0.05, 0.60] and must sum to 1.0 within
their parent. This single shape backs every rubric in the system.
"""
from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WEIGHT_MIN = 0.05
WEIGHT_MAX = 1.0
WEIGHT_TOL = 1e-6
RubricScope = Literal["deliverable", "function", "hire", "vendor", "deal"]


class Attribute(BaseModel):
    """One level on the discrete scoring scale for a Characteristic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: str = Field(description="Human label e.g. 'Mature', 'Developing'.")
    score: int = Field(ge=0, le=4, description="Integer 0..4. Higher is better.")
    anchor: str = Field(min_length=4, description="What this score looks like in practice.")


class Characteristic(BaseModel):
    """Weighted sub-criterion within a Group."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    weight: float = Field(ge=WEIGHT_MIN, le=WEIGHT_MAX)
    attributes: tuple[Attribute, ...] = Field(min_length=2)

    @field_validator("attributes")
    @classmethod
    def _unique_scores(cls, attrs: tuple[Attribute, ...]) -> tuple[Attribute, ...]:
        scores = [a.score for a in attrs]
        if len(set(scores)) != len(scores):
            raise ValueError("attribute scores must be unique within a characteristic")
        return attrs


class Group(BaseModel):
    """Weighted top-level dimension."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    weight: float = Field(ge=WEIGHT_MIN, le=WEIGHT_MAX)
    characteristics: tuple[Characteristic, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _characteristic_weights_sum_to_one(self) -> Group:
        total = sum(c.weight for c in self.characteristics)
        if not math.isclose(total, 1.0, abs_tol=WEIGHT_TOL):
            raise ValueError(
                f"group '{self.id}': characteristic weights sum to {total:.4f}, must be 1.0"
            )
        return self


class Rubric(BaseModel):
    """Top-level rubric definition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rubric_id: str = Field(pattern=r"^rb\.[a-z]+\.[a-z0-9_]+$")
    scope: RubricScope
    name: str
    version: int = Field(ge=1)
    description: str | None = None
    groups: tuple[Group, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _group_weights_sum_to_one(self) -> Rubric:
        total = sum(g.weight for g in self.groups)
        if not math.isclose(total, 1.0, abs_tol=WEIGHT_TOL):
            raise ValueError(
                f"rubric '{self.rubric_id}': group weights sum to {total:.4f}, must be 1.0"
            )
        return self

    @property
    def max_score(self) -> int:
        first_chars = self.groups[0].characteristics
        return max(a.score for a in first_chars[0].attributes)


# ---------------------------- scoring inputs / outputs ----------------------------


class CharacteristicScore(BaseModel):
    """A single grader judgment on one characteristic."""

    model_config = ConfigDict(extra="forbid")

    characteristic_id: str
    score: int = Field(ge=0, le=4)
    rationale: str = Field(min_length=1)


class RubricScoreReport(BaseModel):
    """Aggregated scoring result for one rubric application."""

    model_config = ConfigDict(extra="forbid")

    rubric_id: str
    target_id: str
    scores: tuple[CharacteristicScore, ...]
    weighted_total: float
    normalized_pct: float
    passed: bool

    @classmethod
    def compute(
        cls,
        rubric: Rubric,
        target_id: str,
        scores: list[CharacteristicScore],
        pass_threshold_pct: float = 70.0,
    ) -> RubricScoreReport:
        score_by_id = {s.characteristic_id: s.score for s in scores}
        weighted = 0.0
        for group in rubric.groups:
            for char in group.characteristics:
                if char.id not in score_by_id:
                    raise ValueError(f"missing score for characteristic '{char.id}'")
                weighted += group.weight * char.weight * score_by_id[char.id]
        normalized = (weighted / rubric.max_score) * 100.0
        return cls(
            rubric_id=rubric.rubric_id,
            target_id=target_id,
            scores=tuple(scores),
            weighted_total=weighted,
            normalized_pct=normalized,
            passed=normalized >= pass_threshold_pct,
        )
