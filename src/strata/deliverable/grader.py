"""LLM-based grading using raw API calls."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel

from strata.deliverable.base import Deliverable, Grade, Rubric

if TYPE_CHECKING:
    from openai import OpenAI


class Grader:
    """Grades deliverables against rubrics using LLM API calls.

    This grader uses raw OpenAI completions and parses the JSON response
    manually into a Grade object.
    """

    def __init__(self, client: OpenAI, model: str = "gpt-4o-mini"):
        self._client = client
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
            f"Max score: {rubric.max_score}\n\n"
            f"Return a JSON object with:\n"
            f'- "overall_score": float,\n'
            f'- "criterion_scores": list of {{"criterion": str, "score": float, "reasoning": str}},\n'
            f'- "summary": str,\n'
            f'- "strengths": list of str,\n'
            f'- "improvements": list of str\n'
        )

    def grade(self, deliverable: Deliverable, rubric: Rubric) -> Grade:
        """Grade a deliverable against a rubric using an LLM."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": self._build_prompt(deliverable, rubric)}],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        return Grade(**data)
