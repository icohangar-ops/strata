"""L4 — Deliverable Factory.

Loop:
    persona prompt  ->  author draft  ->  grader  ->  pass? else feedback -> revise
    until passed OR max_iterations reached.

Authoring is delegated to a callable so this file knows nothing about LLMs.
The default authoring callable is a Mock that produces increasingly compliant
drafts each iteration (enough to demonstrate the loop in tests).

If an ExemplarStore is provided, the factory queries it once at the start of
the run for top-K similar past drafts of the same chain and injects them into
inputs under `_exemplars` for the author prompt to splice in. This is purely
additive — when the store is None or empty, behavior is unchanged.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from strata.config import get_settings
from strata.deliverable.grader import Grader, GraderResult
from strata.deliverable.persona import Persona, get_persona
from strata.schema import Rubric
from strata.vector import ExemplarStore, NullExemplarStore

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
        exemplar_store: ExemplarStore | None = None,
        chain_id: str | None = None,
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
        self.exemplar_store: ExemplarStore = exemplar_store or NullExemplarStore()
        self.chain_id = chain_id  # optional; used to scope exemplar lookups
        self.exemplar_top_k = s.exemplar_top_k

    def run(self, target_id: str, inputs: dict[str, Any]) -> FactoryResult:
        history: list[GraderResult] = []
        draft = ""
        last: GraderResult | None = None

        # One exemplar fetch per run — same exemplars feed every revise iteration.
        exemplars = self._fetch_exemplars(target_id, inputs)
        # Build the author-side inputs once; per-iteration mutations stay local.
        author_inputs_template: dict[str, Any] = dict(inputs)
        if exemplars:
            author_inputs_template["_exemplars"] = exemplars

        for i in range(1, self.max_iterations + 1):
            iteration_inputs = dict(author_inputs_template)
            draft = self.author(self.persona, self.rubric, iteration_inputs, history)
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

    def _fetch_exemplars(self, target_id: str, inputs: dict[str, Any]) -> list[dict]:
        """Build a query string from inputs and pull top-K similar past drafts."""
        if self.chain_id is None:
            return []
        query_parts = [self.rubric.name, target_id]
        for key in ("company", "period", "deal_period", "as_of", "project_name"):
            if key in inputs and isinstance(inputs[key], (str, int, float)):
                query_parts.append(str(inputs[key]))
        query = " ".join(query_parts)
        try:
            hits = self.exemplar_store.search(
                chain_id=self.chain_id, query=query, top_k=self.exemplar_top_k
            )
        except Exception:
            # Vector lookup is purely additive — never fail a run because of it.
            return []
        return [
            {
                "target_id": h.exemplar.target_id,
                "draft": h.exemplar.draft,
                "similarity": h.similarity,
                "score_pct": h.exemplar.score_pct,
            }
            for h in hits
        ]
