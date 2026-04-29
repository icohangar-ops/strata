"""L3 — Director.

v2: routes a job to a Chain (resolved either by name or dynamically from L1+L2),
then executes it via the L4 deliverable factory and persists artifacts.

LLM choice is a Director-level toggle (`use_llm`). Mock by default — the same
mock author/grader pair the test suite uses. When `use_llm=True`, the grader
swaps to AnthropicLLM and the author swaps to the Anthropic-backed author.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from strata import registry
from strata.catalog import load_catalog
from strata.deliverable.factory import Author, DeliverableFactory, FactoryResult
from strata.deliverable.grader import Grader, MockLLM
from strata.maturity.assessor import AssessmentResult
from strata.models import Rubric as RubricRow
from strata.models import RubricScore as RubricScoreRow
from strata.models import RunLog as RunLogRow
from strata.orchestrator.chains import Chain, all_chains, chain_for_deliverable


@dataclass(frozen=True)
class DirectorRun:
    run_id: str
    chain_id: str
    factory_result: FactoryResult


@dataclass(frozen=True)
class RouteDecision:
    chain: Chain
    weakest_capability: str
    weakest_pct: float
    rationale: str
    alternates: tuple[Chain, ...] = ()
    preferred_signal: str | None = None  # set when inputs.preferred_deliverable selected the chain


class Director:
    """Routes a job to a chain and persists run artifacts."""

    def __init__(self, persist: bool = True, use_llm: bool = False) -> None:
        self._persist = persist
        self._use_llm = use_llm

    # ---------------------------- public API ----------------------------

    def run_board_pack(self, inputs: dict[str, Any]) -> DirectorRun:
        """v1 entrypoint kept for back-compat. Always routes to the board-pack chain."""
        chain = chain_for_deliverable("rb.deliverable.board_pack")
        return self._run_chain(chain, inputs)

    def run_chain(self, chain_id: str, inputs: dict[str, Any]) -> DirectorRun:
        """Run a chain by its id."""
        chain = next((c for c in all_chains() if c.chain_id == chain_id), None)
        if chain is None:
            raise KeyError(f"unknown chain '{chain_id}'. known: {[c.chain_id for c in all_chains()]}")
        return self._run_chain(chain, inputs)

    def route(
        self,
        assessment: AssessmentResult,
        inputs: dict[str, Any],
    ) -> tuple[RouteDecision, DirectorRun]:
        """Pick a chain dynamically from the L1 heatmap and L2 catalog, then run it.

        If `inputs.preferred_deliverable` names a deliverable rubric_id that targets
        the weakest capability, that chain wins and the rationale notes the user signal.
        """
        decision = self.decide(assessment, preferred_deliverable=inputs.get("preferred_deliverable"))
        run = self._run_chain(decision.chain, inputs)
        return decision, run

    def decide(
        self,
        assessment: AssessmentResult,
        preferred_deliverable: str | None = None,
    ) -> RouteDecision:
        """Pure decision: weakest capability that has an executable chain wins.

        Selection rules:
            1. Capability rank: lowest score_pct first, then capability rubric_id ascending.
            2. Chain pick within a capability:
                 a. If `preferred_deliverable` matches a candidate, that wins.
                 b. Else chain whose chain_id sorts first.
        """
        cap_to_chains = self._capability_chain_index()
        ranked = sorted(assessment.capabilities, key=lambda c: (c.score_pct, c.rubric.rubric_id))
        for snap in ranked:
            cap_id = snap.rubric.rubric_id
            if cap_id not in cap_to_chains:
                continue
            candidates = cap_to_chains[cap_id]
            preferred_hit: Chain | None = None
            if preferred_deliverable:
                preferred_hit = next(
                    (c for c in candidates if c.rubric_id == preferred_deliverable), None
                )
            chosen = preferred_hit or candidates[0]
            alternates = tuple(c for c in candidates if c.chain_id != chosen.chain_id)
            if preferred_hit:
                rationale = (
                    f"weakest capability '{cap_id}' at {snap.score_pct:.1f}%; "
                    f"user-preferred deliverable '{preferred_deliverable}' selected "
                    f"chain '{chosen.chain_id}' from {len(candidates)} candidates"
                )
                signal = preferred_deliverable
            else:
                tiebreak_note = (
                    "" if len(candidates) == 1
                    else f" (chose '{chosen.chain_id}' from {len(candidates)} candidates by chain_id sort)"
                )
                rationale = (
                    f"weakest capability '{cap_id}' at {snap.score_pct:.1f}% "
                    f"has executable chain '{chosen.chain_id}'{tiebreak_note}"
                )
                signal = None
            return RouteDecision(
                chain=chosen,
                weakest_capability=cap_id,
                weakest_pct=snap.score_pct,
                rationale=rationale,
                alternates=alternates,
                preferred_signal=signal,
            )
        raise RuntimeError(
            "no capability in the assessment maps to an executable chain in the catalog"
        )

    @staticmethod
    def _capability_chain_index() -> dict[str, list[Chain]]:
        """Catalog-driven map: capability rubric_id -> sorted list of executable chains."""
        catalog = load_catalog()
        chains_by_rubric = {c.rubric_id: c for c in all_chains()}
        out: dict[str, list[Chain]] = {}
        for skill in (s for p in catalog.phases for s in p.skills):
            if not (skill.deliverable_rubric and skill.capability):
                continue
            ch = chains_by_rubric.get(skill.deliverable_rubric)
            if ch is None:
                continue
            bucket = out.setdefault(skill.capability, [])
            if ch.chain_id not in {c.chain_id for c in bucket}:
                bucket.append(ch)
        for cap_id in out:
            out[cap_id].sort(key=lambda c: c.chain_id)
        return out

    def plan_90_days(self, assessment: AssessmentResult, axis: str = "function"):
        """Adapter to maturity.roadmap.plan_90_days, exposed on the Director for
        symmetry with route() / decide()."""
        from strata.maturity.roadmap import plan_90_days
        return plan_90_days(assessment, axis=axis)

    def chains_for_capability(self, capability_rubric_id: str) -> list[Chain]:
        """All chains whose deliverable is referenced by a skill targeting this capability."""
        catalog = load_catalog()
        chains_by_rubric = {c.rubric_id: c for c in all_chains()}
        out: list[Chain] = []
        seen: set[str] = set()
        for skill in (s for p in catalog.phases for s in p.skills):
            if skill.capability == capability_rubric_id and skill.deliverable_rubric:
                ch = chains_by_rubric.get(skill.deliverable_rubric)
                if ch and ch.chain_id not in seen:
                    out.append(ch)
                    seen.add(ch.chain_id)
        return sorted(out, key=lambda c: c.chain_id)

    # ---------------------------- chain execution ----------------------------

    def _run_chain(
        self,
        chain: Chain,
        inputs: dict[str, Any],
        _running: set[str] | None = None,
    ) -> DirectorRun:
        """Execute a chain. If the chain has dependencies, execute them first
        (depth-first, cycle-checked) and inject their final drafts under
        inputs['upstream'][upstream_chain_id]. Each chain's perception adapter
        runs once before authoring."""
        _running = _running or set()
        if chain.chain_id in _running:
            raise RuntimeError(f"chain dependency cycle detected at '{chain.chain_id}'")
        _running = _running | {chain.chain_id}

        upstream_drafts: dict[str, str] = {}
        for dep_id in chain.depends_on:
            dep_chain = next((c for c in all_chains() if c.chain_id == dep_id), None)
            if dep_chain is None:
                raise KeyError(f"chain '{chain.chain_id}' depends on unknown chain '{dep_id}'")
            dep_run = self._run_chain(dep_chain, inputs, _running=_running)
            upstream_drafts[dep_id] = dep_run.factory_result.final_draft

        enriched_inputs = dict(inputs)
        if upstream_drafts:
            enriched_inputs["upstream"] = upstream_drafts
        if chain.perception is not None:
            enriched_inputs = chain.perception(enriched_inputs)

        rubric = registry.get(chain.rubric_id)
        target_id = self._target_id(enriched_inputs)
        run_log_id = uuid.uuid4()
        if self._persist:
            self._open_run_log(run_log_id, chain, enriched_inputs)

        try:
            factory = self._build_factory(chain, rubric)
            result = factory.run(target_id=target_id, inputs=enriched_inputs)
            if self._persist:
                self._persist_scores(run_log_id, rubric, result)
                self._close_run_log(
                    run_log_id,
                    status="passed" if result.passed else "failed",
                    outputs={
                        "draft": result.final_draft,
                        "iterations": result.iterations,
                        "passed": result.passed,
                        "upstream_chains": list(upstream_drafts.keys()),
                    },
                )
            return DirectorRun(
                run_id=str(run_log_id), chain_id=chain.chain_id, factory_result=result
            )
        except Exception as e:
            if self._persist:
                self._close_run_log(run_log_id, status="error", outputs=None, error=str(e))
            raise

    def _build_factory(self, chain: Chain, rubric) -> DeliverableFactory:
        if self._use_llm:
            from strata.config import get_settings
            backend = get_settings().llm_backend
            if backend == "anthropic":
                from strata.deliverable.author import anthropic_author_factory
                from strata.deliverable.grader import AnthropicLLM

                author: Author = anthropic_author_factory()
                grader = Grader(llm=AnthropicLLM(), pass_threshold_pct=70.0)
            elif backend == "openai":
                from strata.deliverable.author import openai_compatible_author_factory
                from strata.deliverable.grader import OpenAICompatibleLLM

                author = openai_compatible_author_factory()
                grader = Grader(llm=OpenAICompatibleLLM(), pass_threshold_pct=70.0)
            else:
                raise ValueError(
                    f"unknown STRATA_LLM_BACKEND='{backend}'; expected 'openai' or 'anthropic'"
                )
        else:
            author = chain.mock_author
            grader = Grader(llm=MockLLM(), pass_threshold_pct=70.0)
        return DeliverableFactory(rubric=rubric, author=author, grader=grader)

    # ---------------------------- persistence helpers ----------------------------

    @staticmethod
    def _target_id(inputs: dict[str, Any]) -> str:
        company = inputs.get("company", "company")
        period = inputs.get("period", "period")
        return f"{company}::{period}".lower().replace(" ", "_")

    @staticmethod
    def _hash_inputs(inputs: dict[str, Any]) -> str:
        blob = json.dumps(inputs, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def _open_run_log(self, run_id: uuid.UUID, chain: Chain, inputs: dict[str, Any]) -> None:
        from strata.db import session_scope

        with session_scope() as s:
            s.add(
                RunLogRow(
                    id=run_id,
                    chain_id=chain.chain_id,
                    inputs_hash=self._hash_inputs(inputs),
                    started_at=datetime.now(timezone.utc),
                    status="running",
                    inputs=inputs,
                )
            )

    def _close_run_log(
        self,
        run_id: uuid.UUID,
        status: str,
        outputs: dict[str, Any] | None,
        error: str | None = None,
    ) -> None:
        from strata.db import session_scope

        with session_scope() as s:
            row = s.get(RunLogRow, run_id)
            if row is None:
                return
            row.status = status
            row.finished_at = datetime.now(timezone.utc)
            row.outputs = outputs
            row.error = error

    def _persist_scores(self, run_id: uuid.UUID, rubric, result: FactoryResult) -> None:
        from strata.db import session_scope

        with session_scope() as s:
            row = s.execute(
                select(RubricRow).where(
                    RubricRow.rubric_id == rubric.rubric_id,
                    RubricRow.version == rubric.version,
                )
            ).scalar_one_or_none()
            if row is None:
                row = RubricRow(
                    id=uuid.uuid4(),
                    rubric_id=rubric.rubric_id,
                    scope=rubric.scope,
                    name=rubric.name,
                    version=rubric.version,
                    definition=rubric.model_dump(mode="json"),
                )
                s.add(row)
                s.flush()
            for i, gr in enumerate(result.history, start=1):
                s.add(
                    RubricScoreRow(
                        id=uuid.uuid4(),
                        rubric_db_id=row.id,
                        target_id=result.target_id,
                        target_kind="deliverable",
                        iteration=i,
                        weighted_total=gr.report.weighted_total,
                        normalized_pct=gr.report.normalized_pct,
                        passed=gr.report.passed,
                        detail={"scores": [s.model_dump() for s in gr.report.scores]},
                        run_log_id=run_id,
                    )
                )
