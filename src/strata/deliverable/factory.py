"""L4 — Deliverable Factory.

Loop:
    persona prompt  ->  author draft  ->  grader  ->  pass? else feedback -> revise
    until passed OR max_iterations reached.

Authoring is delegated to a callable so this file knows nothing about LLMs.
The default authoring callable is a Mock that produces increasingly compliant
drafts each iteration (enough to demonstrate the loop in tests).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from strata.config import get_settings
from strata.deliverable.grader import Grader, GraderResult
from strata.deliverable.persona import Persona, get_persona
from strata.schema import Rubric

Author = Callable[[Persona, Rubric, dict[str, Any], list[GraderResult]], str]


@dataclass(frozen=True)
class FactoryResult:
    target_id: str
    rubric_id: str
    iterations: int
    final_draft: str
    final_report: GraderResult
    history: tuple[GraderResult, ...] = field(default_factory=tuple)
    passed: bool = False


class DeliverableFactory:
    def __init__(
        self,
        rubric: Rubric,
        author: Author,
        grader: Grader | None = None,
        max_iterations: int | None = None,
        pass_threshold_pct: float | None = None,
    ) -> None:
        s = get_settings()
        self.rubric = rubric
        self.author = author
        # threshold is expressed as a percentage of the rubric's max score
        self.pass_pct = (
            pass_threshold_pct
            if pass_threshold_pct is not None
            else (s.pass_threshold / rubric.max_score) * 100.0
        )
        self.grader = grader or Grader(pass_threshold_pct=self.pass_pct)
        self.max_iterations = max_iterations or s.max_iterations
        self.persona = get_persona(rubric.rubric_id)

    def run(self, target_id: str, inputs: dict[str, Any]) -> FactoryResult:
        history: list[GraderResult] = []
        draft = ""
        last: GraderResult | None = None
        for i in range(1, self.max_iterations + 1):
            draft = self.author(self.persona, self.rubric, inputs, history)
            last = self.grader.grade(self.rubric, draft, target_id=target_id)
            history.append(last)
            if last.report.passed:
                return FactoryResult(
                    target_id=target_id,
                    rubric_id=self.rubric.rubric_id,
                    iterations=i,
                    final_draft=draft,
                    final_report=last,
                    history=tuple(history),
                    passed=True,
                )
        assert last is not None
        return FactoryResult(
            target_id=target_id,
            rubric_id=self.rubric.rubric_id,
            iterations=self.max_iterations,
            final_draft=draft,
            final_report=last,
            history=tuple(history),
            passed=False,
        )
