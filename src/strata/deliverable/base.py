"""Base models for deliverables and grading rubrics."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class Score(Enum):
    """Standard grading scale."""

    EXCELLENT = 5
    GOOD = 4
    ADEQUATE = 3
    NEEDS_WORK = 2
    POOR = 1


class RubricCriterion(BaseModel):
    """A single criterion within a grading rubric."""

    name: str = Field(description="Name of the criterion")
    description: str = Field(description="What this criterion evaluates")
    weight: float = Field(default=1.0, ge=0.0, le=10.0, description="Weight of this criterion in the overall score")


class Rubric(BaseModel):
    """A grading rubric composed of criteria."""

    name: str = Field(description="Name of the rubric")
    criteria: list[RubricCriterion] = Field(default_factory=list, description="Grading criteria")
    max_score: float = Field(default=5.0, description="Maximum possible score")


class CriterionScore(BaseModel):
    """Score for a single criterion."""

    criterion: str = Field(description="Name of the criterion")
    score: float = Field(description="Score awarded for this criterion")
    reasoning: str = Field(description="Explanation for the score")


class Grade(BaseModel):
    """A structured grade for a deliverable."""

    overall_score: float = Field(description="Overall weighted score")
    criterion_scores: list[CriterionScore] = Field(default_factory=list, description="Per-criterion breakdown")
    summary: str = Field(description="Brief summary of the grading result")
    strengths: list[str] = Field(default_factory=list, description="Noted strengths")
    improvements: list[str] = Field(default_factory=list, description="Suggested improvements")


class Deliverable(BaseModel):
    """A deliverable to be graded."""

    name: str = Field(description="Name or title of the deliverable")
    content: str = Field(description="The text content of the deliverable")
    metadata: dict = Field(default_factory=dict, description="Optional metadata about the deliverable")
