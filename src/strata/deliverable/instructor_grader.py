"""Structured LLM grading using instructor for enforced Pydantic outputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from strata.deliverable.base import Deliverable, Grade, Rubric

if TYPE_CHECKING:
    from openai import OpenAI


class RubricResponse(BaseModel):
    """Pydantic schema enforced by instructor on LLM grading responses."""

    overall_score: float = Field(description="Overall weighted score")
    criterion_scores: list[CriterionScoreResponse] = Field(
        default_factory=list, description="Per-criterion breakdown"
    )
    summary: str = Field(description="Brief summary of the grading result")
    strengths: list[str] = Field(default_factory=list, description="Noted strengths")
    improvements: list[str] = Field(default_factory=list, description="Suggested improvements")


class CriterionScoreResponse(BaseModel):
    """Score for a single criterion in the structured response."""

    criterion: str = Field(description="Name of the criterion")
    score: float = Field(description="Score awarded for this criterion")
    reasoning: str = Field(description="Explanation for the score")


RubricResponse.model_rebuild()


class InstructorGrader:
    """Grades deliverables using instructor for enforced structured outputs.

    Unlike the base Grader which relies on JSON parsing and manual validation,
    this grader uses instructor to enforce Pydantic schema compliance at the
    API level, ensuring every LLM response conforms to RubricResponse.
    """

    def __init__(self, client: OpenAI, model: str = "gpt-4o-mini"):
        import instructor

        self._client = instructor.from_openai(client)
        self._model = model

    def _build_prompt(self, deliverable: Deliverable, rubric: Rubric) -> str:
        rubric_text = "\n".join(
            f"- {c.name} (weight={c.weight}): {c.description}"
            for c in rubric.criteria
        )
        return (
            f"You are an expert grader. Grade the following deliverable.\n\n"
            f"Deliverable: {deliverable.name}\n"
            f"Content:\n{deliverable.content}\n\n"
            f"Rubric: {rubric.name}\n"
            f"Criteria:\n{rubric_text}\n"
            f"Max score: {rubric.max_score}"
        )

    def grade(self, deliverable: Deliverable, rubric: Rubric) -> Grade:
        """Grade a deliverable against a rubric using structured LLM output."""
        response = self._client.chat.completions.create(
            model=self._model,
            response_model=RubricResponse,
            messages=[{"role": "user", "content": self._build_prompt(deliverable, rubric)}],
            max_retries=3,
        )
        return Grade(
            overall_score=response.overall_score,
            criterion_scores=[
                {"criterion": cs.criterion, "score": cs.score, "reasoning": cs.reasoning}
                for cs in response.criterion_scores
            ],
            summary=response.summary,
            strengths=response.strengths,
            improvements=response.improvements,
        )
